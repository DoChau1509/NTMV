from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import SubItem, EvaluationDetail
from .evaluation_session_service import EvaluationSession

def save_evaluation_draft_bulk(*, evaluation, scores_data, note=None, user=None, client_version=None, request=None, recalculate_fn=None, rebalance_fn=None):
    """
    Perform a batch validation, collect dirty fields, and execute bulk DB operations
    for saving student evaluation draft scores/notes with Workflow Guard validation.
    """
    # 1. Workflow Guard validation
    from .workflow_guard import validate_evaluation_write_access
    validate_evaluation_write_access(
        evaluation=evaluation,
        user=user,
        client_version=client_version,
        request=request
    )

    # 2. Batch Validation - Active Evaluation Session
    is_student = user.role == 'student' if user else True
    if is_student:
        session_exists = EvaluationSession.objects.filter(
            evaluation=evaluation, status='active'
        ).exists() or EvaluationSession.objects.filter(
            student=evaluation.student, semester=evaluation.semester, year=evaluation.year, status='active'
        ).exists() or EvaluationSession.objects.filter(
            semester=evaluation.semester, year=evaluation.year, student__isnull=True, status='active'
        ).exists()
        
        if not session_exists:
            raise ValidationError('Phiếu đánh giá không có phiên hoạt động hợp lệ.')

    # 3. Batch Validation - Criteria & Scores Limit
    manual_subitems = SubItem.objects.filter(
        group__criterion__criteria_set=evaluation.criteria_set,
        group__criterion__is_manual=True,
    )
    manual_subitem_dict = {sub.id: sub for sub in manual_subitems}

    # Validate all incoming scores first
    valid_scores_to_process = {}
    for sub_item_id, score_val in scores_data.items():
        try:
            sub_item_id_int = int(sub_item_id)
        except (ValueError, TypeError):
            raise ValidationError(f"Mã tiêu chí {sub_item_id} không hợp lệ.")

        if sub_item_id_int not in manual_subitem_dict:
            continue

        sub_item = manual_subitem_dict[sub_item_id_int]
        try:
            score = int(float(score_val or 0))
        except (ValueError, TypeError):
            raise ValidationError(f"Điểm số cho tiêu chí {sub_item.name[:20]}... không đúng định dạng số.")

        # Check score limit: max_score can be negative (penalty)
        if sub_item.max_score >= 0:
            if score < 0 or score > sub_item.max_score:
                raise ValidationError(f"Điểm số của '{sub_item.name[:30]}' phải từ 0 đến {sub_item.max_score}.")
        else:
            if score > 0 or score < sub_item.max_score:
                raise ValidationError(f"Điểm số của '{sub_item.name[:30]}' phải từ {sub_item.max_score} đến 0.")

        valid_scores_to_process[sub_item_id_int] = (sub_item, score)

    # 4. Atomic Transaction and Bulk Execution
    autosave_count = 0
    with transaction.atomic():
        has_changes = False
        if valid_scores_to_process:
            # Fetch existing details for these subitems
            existing_details = EvaluationDetail.objects.filter(
                evaluation=evaluation,
                sub_item_id__in=valid_scores_to_process.keys()
            )
            existing_details_dict = {det.sub_item_id: det for det in existing_details}

            bulk_creates = []
            bulk_updates = []

            for sub_item_id, (sub_item, score) in valid_scores_to_process.items():
                if sub_item_id in existing_details_dict:
                    detail = existing_details_dict[sub_item_id]
                    if detail.score != score or detail.is_rejected:
                        detail.score = score
                        detail.is_rejected = False
                        detail.reject_reason = None
                        bulk_updates.append(detail)
                        autosave_count += 1
                        has_changes = True
                else:
                    detail = EvaluationDetail(
                        evaluation=evaluation,
                        sub_item=sub_item,
                        score=score,
                        is_rejected=False,
                        reject_reason=None
                    )
                    bulk_creates.append(detail)
                    autosave_count += 1
                    has_changes = True

            if bulk_creates:
                EvaluationDetail.objects.bulk_create(bulk_creates)
            if bulk_updates:
                EvaluationDetail.objects.bulk_update(bulk_updates, fields=['score', 'is_rejected', 'reject_reason'])

        # Save evaluation note if modified
        if note is not None and evaluation.note != note:
            evaluation.note = note
            evaluation.save(update_fields=['note'])
            autosave_count += 1
            has_changes = True

        # Increment version if there are database changes
        if has_changes:
            evaluation.version += 1
            evaluation.save(update_fields=['version'])

        # Recalculate score and rebalance student training score
        if recalculate_fn:
            recalculate_fn(evaluation)
        if rebalance_fn:
            rebalance_fn(evaluation.student)
        evaluation.refresh_from_db()

    return {
        'success': True,
        'saved_at': timezone.now().isoformat(),
        'autosave_count': autosave_count,
        'total_score': evaluation.total_score,
        'classification': evaluation.classification,
        'serverVersion': evaluation.version
    }


import threading
from django import db
from ..models import EvaluationJob, Evaluation, Student, CriteriaSet, SubItem, EvaluationDetail
from ..views import sync_evaluation_with_transcript, recalculate_evaluation_score, rebalance_training_score

def async_bulk_init_evaluations(job_id, payload_data):
    """
    Background worker to create/update evaluations for students in chunks.
    """
    db.close_old_connections()
    try:
        job = EvaluationJob.objects.get(id=job_id)
        job.status = 'RUNNING'
        job.save()

        total = len(payload_data)
        completed = 0
        batch_size = 50 # Small batches to avoid SQLite locks

        # Group data into batches
        batches = [payload_data[i:i + batch_size] for i in range(0, total, batch_size)]

        for batch in batches:
            with transaction.atomic():
                for row in batch:
                    student_id = row.get('studentId') or row.get('student_id')
                    try:
                        student = Student.objects.get(student_id=student_id)
                    except Student.DoesNotExist:
                        continue
                    semester = row.get('semester')
                    year = row.get('year')
                    scores_data = row.get('scores', {})
                    note = row.get('note', '')
                    academic_gpa = row.get('academicGpa') or row.get('academic_gpa')
                    academic_classification = row.get('academicClassification') or row.get('academic_classification', '')
                    requested_raw_score = row.get('rawScore') or row.get('raw_score')
                    requested_set_id = row.get('criteriaSet') or row.get('criteria_set')

                    if requested_set_id:
                        try:
                            criteria_set = CriteriaSet.objects.get(pk=requested_set_id)
                        except CriteriaSet.DoesNotExist:
                            continue
                    else:
                        criteria_set = (
                            CriteriaSet.objects.filter(semester=semester, academic_year=year, is_active=True).first()
                            or CriteriaSet.objects.filter(is_active=True).first()
                        )

                    if not criteria_set:
                        continue

                    # Create or update evaluation
                    evaluation, created = Evaluation.objects.update_or_create(
                        student=student, semester=semester, year=year,
                        defaults={
                            'note': note,
                            'academic_gpa': academic_gpa if academic_gpa not in ('', None) else None,
                            'academic_classification': academic_classification or '',
                            'status': 'published',
                            'class_confirmed': False,
                            'criteria_set': criteria_set,
                        }
                    )

                    # Clear old details
                    evaluation.details.all().delete()

                    # Write new details and calculate total score
                    detail_objects = []
                    for sub_item_id, score_val in scores_data.items():
                        try:
                            sub_item = SubItem.objects.get(
                                id=int(sub_item_id),
                                group__criterion__criteria_set=criteria_set
                            )
                            detail_objects.append(
                                EvaluationDetail(
                                    evaluation=evaluation,
                                    sub_item=sub_item,
                                    score=score_val
                                )
                            )
                        except (SubItem.DoesNotExist, ValueError):
                            pass
                    
                    if detail_objects:
                        EvaluationDetail.objects.bulk_create(detail_objects)

                    sync_evaluation_with_transcript(evaluation)
                    recalculate_evaluation_score(evaluation)
                    if requested_raw_score not in (None, ''):
                        requested_total = int(float(requested_raw_score))
                        if requested_total > evaluation.raw_score:
                            evaluation.raw_score = requested_total
                            evaluation.save(update_fields=('raw_score',))
                    rebalance_training_score(student)
                    completed += 1
                    
                    try:
                        from drl_app.models import User, SystemConfig
                        from drl_app.views import create_notification
                        from django.core.mail import send_mail
                        from django.conf import settings

                        semester_display = semester if str(semester).startswith("HK") or str(semester).startswith("Học kỳ") else f"HK{semester}"
                        
                        student_user = User.objects.filter(student_id=student.student_id).first()
                        if student_user:
                            create_notification(
                                user=student_user,
                                title="Mở đợt đánh giá rèn luyện mới",
                                message=f"Hệ thống đã mở đợt tự đánh giá rèn luyện cho {semester_display} {year}. Vui lòng tự chấm điểm của bạn trước hạn chót.",
                                type='evaluation',
                                level='info',
                                action_url='/'
                            )
                        
                        if student.email:
                            start_date = SystemConfig.objects.filter(key='self_assessment_start').first()
                            deadline_date = SystemConfig.objects.filter(key='self_assessment_deadline').first()
                            
                            def format_dt(dt_str):
                                if not dt_str:
                                    return "Chưa cấu hình"
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(dt_str)
                                    return dt.strftime("%d/%m/%Y %H:%M")
                                except Exception:
                                    try:
                                        dt = datetime.strptime(dt_str, "%Y-%m-%d")
                                        return dt.strftime("%d/%m/%Y")
                                    except Exception:
                                        return dt_str
                            
                            start_val = format_dt(start_date.value if start_date else None)
                            deadline_val = format_dt(deadline_date.value if deadline_date else None)
                            
                            email_subject = f"[ITC Point] Thông báo tự đánh giá điểm rèn luyện {semester_display} {year}"
                            email_message = f"Chào {student.full_name},\n\nCổng tự đánh giá điểm rèn luyện trực tuyến đã chính thức được mở cho {semester_display} năm học {year}.\nVui lòng đăng nhập và thực hiện tự đánh giá trước hạn chót: {deadline_val}."
                            
                            email_html = f"""
<div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.05); background-color: #ffffff;">
  <div style="background: linear-gradient(135deg, #6366f1, #a855f7); padding: 32px 24px; text-align: center; color: white;">
    <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">Thông Báo Đánh Giá ĐRL</h1>
    <p style="margin: 4px 0 0 0; font-size: 13px; color: rgba(255,255,255,0.85); font-weight: 500;">Bắt đầu đợt tự đánh giá điểm rèn luyện</p>
  </div>
  <div style="padding: 40px 32px; background-color: #ffffff;">
    <h2 style="margin-top: 0; color: #1e293b; font-size: 20px; font-weight: 700; letter-spacing: -0.5px;">Chào {student.full_name},</h2>
    <p style="color: #475569; line-height: 1.6; font-size: 15px; margin-top: 12px;">Hệ thống thông báo: Cổng tự đánh giá điểm rèn luyện trực tuyến đã chính thức được mở. Vui lòng truy cập hệ thống để hoàn thành phiếu tự chấm điểm rèn luyện cá nhân:</p>
    
    <div style="background-color: #f8fafc; border-radius: 12px; padding: 20px; margin: 28px 0; border: 1px solid #f1f5f9; border-left: 4px solid #6366f1;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; width: 150px; text-transform: uppercase; letter-spacing: 0.5px;">Học kỳ / Năm học:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: 700;">{semester_display} - Năm học {year}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Ngày mở cổng:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: 500;">{start_val}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Hạn cuối tự chấm:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #ef4444; font-weight: 700;">{deadline_val}</td>
        </tr>
      </table>
    </div>

    <div style="text-align: center; margin: 36px 0 28px 0;">
      <a href="http://localhost:8080/" style="background: linear-gradient(135deg, #6366f1, #a855f7); color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 10px; font-weight: 700; font-size: 15px; display: inline-block; box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.3); letter-spacing: -0.2px;">Thực hiện tự đánh giá</a>
    </div>

    <div style="background-color: #fef2f2; border-radius: 8px; padding: 14px 18px; border: 1px solid #fee2e2; margin-top: 24px;">
      <p style="color: #b91c1c; font-size: 13px; font-weight: 600; margin: 0; line-height: 1.5;">
        * Lưu ý: Sau thời hạn nêu trên, hệ thống sẽ tự động đóng. Những sinh viên không tự chấm điểm sẽ nhận điểm 0 rèn luyện cho học kỳ này.
      </p>
    </div>
  </div>
  <div style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #f1f5f9; color: #94a3b8; font-size: 12px; line-height: 1.5;">
    <p style="margin: 0 0 6px 0; font-weight: 500;">Email này được hệ thống ITC Point gửi tự động.</p>
    <p style="margin: 0;">© 2026 ITC Point. All rights reserved.</p>
  </div>
</div>
"""
                            send_mail(
                                email_subject,
                                email_message,
                                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@itcpoint.com'),
                                [student.email],
                                fail_silently=False,
                                html_message=email_html
                            )
                    except Exception as notif_err:
                        print(f"Error creating bulk notification or sending email: {notif_err}")

            # Save progress in database
            job.progress = completed
            job.save()

        job.status = 'SUCCESS'
        job.save()

    except Exception as e:
        try:
            job = EvaluationJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.error_message = str(e)
            job.save()
        except Exception:
            pass
    finally:
        db.close_old_connections()


def launch_bulk_init_job(payload_data):
    """
    Creates a new EvaluationJob and starts a background thread.
    """
    job = EvaluationJob.objects.create(
        status='PENDING',
        progress=0,
        total=len(payload_data)
    )
    threading.Thread(target=async_bulk_init_evaluations, args=(job.id, payload_data), daemon=True).start()
    return job
