import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from drl_app.models import SystemConfig, CriteriaSet, Student, Evaluation, User, StudentClassPosition
from drl_app.views import create_notification

class Command(BaseCommand):
    help = 'Gửi thông báo nhắc nhở hạn chót nộp phiếu DRL hoặc phê duyệt phiếu.'

    def handle(self, *args, **options):
        # 1. Lấy thông tin hạn chót tự đánh giá
        deadline_config = SystemConfig.objects.filter(key='self_assessment_deadline').first()
        if not deadline_config or not deadline_config.value:
            self.stdout.write(self.style.WARNING("Chưa cấu hình hạn chót tự đánh giá."))
            return

        try:
            val = deadline_config.value
            if len(val) == 10:
                deadline_date = timezone.make_aware(timezone.datetime.strptime(val, "%Y-%m-%d") + datetime.timedelta(days=1))
            else:
                deadline_date = timezone.datetime.fromisoformat(val)
                if timezone.is_naive(deadline_date):
                    deadline_date = timezone.make_aware(deadline_date)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Lỗi parse hạn chót: {e}"))
            return

        now = timezone.now()
        time_left = deadline_date - now
        days_left = time_left.days

        self.stdout.write(f"Hạn chót tự đánh giá: {deadline_date}. Còn lại {days_left} ngày.")

        # Lấy bộ tiêu chí hoạt động hiện hành
        active_set = CriteriaSet.objects.filter(is_active=True).first()
        if not active_set:
            self.stdout.write(self.style.WARNING("Không có bộ tiêu chí đang kích hoạt."))
            return

        semester = active_set.semester
        year = active_set.academic_year

        # Gửi nhắc nhở nộp phiếu tự đánh giá cho sinh viên trước 1, 2 hoặc 3 ngày
        if days_left in [1, 2, 3]:
            # Tìm tất cả sinh viên
            students = Student.objects.all()
            for student in students:
                student_user = User.objects.filter(student_id=student.student_id).first()
                if not student_user:
                    continue

                # Kiểm tra xem sinh viên đã nộp phiếu chưa
                has_submitted = Evaluation.objects.filter(
                    student=student,
                    semester=semester,
                    year=year
                ).exclude(status='draft').exists()

                if not has_submitted:
                    create_notification(
                        user=student_user,
                        title=f"Nhắc nhở hạn chót tự chấm DRL: Còn {days_left} ngày",
                        message=f"Hạn chót tự chấm điểm rèn luyện HK{semester} {year} là ngày {val}. Vui lòng hoàn thành phiếu tự chấm của bạn.",
                        type='evaluation',
                        level='warning',
                        action_url='/'
                    )
                    if student.email and days_left in [1, 2]:
                        try:
                            from django.core.mail import send_mail
                            from django.conf import settings
                            email_subject = f"[ITC Point] Nhắc nhở: Còn {days_left} ngày hạn chót tự chấm điểm rèn luyện"
                            semester_display = semester if str(semester).startswith("HK") or str(semester).startswith("Học kỳ") else f"HK{semester}"
                            email_message = f"Chào {student.full_name},\n\nHạn chót tự chấm điểm rèn luyện {semester_display} {year} của bạn là ngày {val}.\nVui lòng đăng nhập hệ thống và nộp phiếu tự chấm trước thời hạn.\n\n* Lưu ý: Nếu quá hạn, bạn sẽ nhận điểm 0 rèn luyện cho học kỳ này."
                            email_html = f"""
<div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); background-color: #ffffff;">
  <div style="background: linear-gradient(135deg, #f59e0b, #d97706); padding: 32px 24px; text-align: center; color: white;">
    <h1 style="margin: 0; font-size: 24px; font-weight: 800;">Sắp Hết Hạn Tự Chấm Điểm</h1>
    <p style="margin: 4px 0 0 0; font-size: 13px; color: rgba(255,255,255,0.85); font-weight: 500;">Còn lại {days_left} ngày để hoàn thành</p>
  </div>
  <div style="padding: 40px 32px; background-color: #ffffff;">
    <h2 style="margin-top: 0; color: #1e293b; font-size: 20px; font-weight: 700;">Chào {student.full_name},</h2>
    <p style="color: #475569; line-height: 1.6; font-size: 15px;">Hệ thống nhắc nhở: Bạn chưa nộp phiếu tự đánh giá điểm rèn luyện cho học kỳ này. Vui lòng thực hiện tự chấm điểm rèn luyện cá nhân trước hạn chót:</p>
    
    <div style="background-color: #fdf2f8; border-radius: 12px; padding: 20px; margin: 28px 0; border: 1px solid #fce7f3; border-left: 4px solid #ef4444;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; width: 150px; text-transform: uppercase;">Học kỳ / Năm học:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: 700;">{semester_display} - Năm học {year}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase;">Hạn cuối nộp:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #ef4444; font-weight: 700;">{val}</td>
        </tr>
      </table>
    </div>

    <div style="text-align: center; margin: 36px 0 28px 0;">
      <a href="http://localhost:8080/" style="background: linear-gradient(135deg, #f59e0b, #d97706); color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 10px; font-weight: 700; font-size: 15px; display: inline-block; box-shadow: 0 10px 15px -3px rgba(245, 158, 11, 0.3);">Bắt đầu tự chấm điểm</a>
    </div>

    <div style="background-color: #fef2f2; border-radius: 8px; padding: 14px 18px; border: 1px solid #fee2e2;">
      <p style="color: #b91c1c; font-size: 13px; font-weight: 600; margin: 0; line-height: 1.5;">
        * Lưu ý quan trọng: Sinh viên không hoàn thành tự chấm điểm đúng hạn sẽ nhận điểm 0 rèn luyện cho học kỳ này.
      </p>
    </div>
  </div>
  <div style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #f1f5f9; color: #94a3b8; font-size: 12px;">
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
                                fail_silently=True,
                                html_message=email_html
                            )
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Error sending email to {student.student_id}: {e}"))
            self.stdout.write(self.style.SUCCESS(f"Đã gửi nhắc nhở nộp phiếu tự chấm cho sinh viên."))

        # Nhắc nhở duyệt phiếu cho lớp trưởng & cố vấn nếu gần đến hạn chót (trong vòng 3 ngày)
        if days_left <= 3:
            # Nhắc lớp trưởng/lớp phó của các lớp có phiếu ở trạng thái 'class_pending'
            class_pending_evals = Evaluation.objects.filter(
                semester=semester,
                year=year,
                status='class_pending'
            )
            classes_needing_class_review = set(class_pending_evals.values_list('student__class_info_id', flat=True))

            for class_id in classes_needing_class_review:
                if not class_id:
                    continue
                # Tìm ban cán sự lớp
                monitors = User.objects.filter(
                    student_id__in=StudentClassPosition.objects.filter(
                        class_info_id=class_id,
                        position__name__in=['Lớp trưởng', 'Lớp phó']
                    ).values_list('student__student_id', flat=True)
                )
                pending_count = class_pending_evals.filter(student__class_info_id=class_id).count()
                for monitor in monitors:
                    create_notification(
                        user=monitor,
                        title="Nhắc nhở duyệt phiếu DRL cấp Lớp",
                        message=f"Lớp của bạn còn {pending_count} phiếu tự đánh giá đang chờ duyệt cấp Lớp. Vui lòng phê duyệt trước hạn chót.",
                        type='evaluation',
                        level='warning',
                        action_url='/class-review'
                    )

            # Nhắc cố vấn của các lớp có phiếu ở trạng thái 'advisor_pending'
            advisor_pending_evals = Evaluation.objects.filter(
                semester=semester,
                year=year,
                status='advisor_pending'
            )
            classes_needing_advisor_review = set(advisor_pending_evals.values_list('student__class_info_id', flat=True))

            for class_id in classes_needing_advisor_review:
                if not class_id:
                    continue
                # Tìm cố vấn lớp
                from drl_app.models import ClassInfo
                clazz = ClassInfo.objects.filter(id=class_id).first()
                if clazz and clazz.advisor:
                    pending_count = advisor_pending_evals.filter(student__class_info_id=class_id).count()
                    create_notification(
                        user=clazz.advisor,
                        title="Nhắc nhở duyệt phiếu DRL cấp Cố vấn",
                        message=f"Lớp {clazz.name} còn {pending_count} phiếu tự đánh giá đang chờ bạn phê duyệt. Vui lòng phê duyệt trước hạn chót.",
                        type='evaluation',
                        level='warning',
                        action_url='/approvals'
                    )
            self.stdout.write(self.style.SUCCESS("Đã gửi nhắc nhở duyệt phiếu tồn đọng cho cán sự và cố vấn."))
