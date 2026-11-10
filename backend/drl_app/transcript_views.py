from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
import time
import threading
from django.core.cache import cache

from .models import AuditLog, ClassInfo, TranscriptImport, TranscriptImportItem, Student
from .services.transcript_statistics import build_summary
from .services.transcript_validator import validate_transcript_upload
from .transcript_serializers import TranscriptImportDetailSerializer, TranscriptImportListSerializer


class AcademicAffairsOrAdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.user.role in ("admin", "academic_affairs", "student_affairs")
        return request.user.role in ("admin", "academic_affairs")


def process_import_async(import_id, user_id):
    try:
        import_record = TranscriptImport.objects.get(id=import_id)
        preview_data = import_record.preview_data or []
        total = len(preview_data)
        
        import_record.status = "PROCESSING"
        import_record.save(update_fields=["status"])
        
        items = []
        for idx, row in enumerate(preview_data):
            time.sleep(0.04) # Simulate processing animation delay
            
            transcript_item = TranscriptImportItem.objects.create(
                transcript_import=import_record,
                student_id=row.get("student_db_id") or None,
                student_code=row.get("student_code") or "",
                full_name=row.get("full_name") or "",
                gpa=row.get("gpa") or 0,
                classification=row.get("classification") or "Yeu",
                status=row.get("match_status") or "NOT_FOUND",
                match_status=row.get("match_status") or "NOT_FOUND",
                remark=row.get("remark") or "",
            )
            items.append({
                "id": transcript_item.id,
                "student": transcript_item.student.id if transcript_item.student else None,
                "student_code": transcript_item.student_code,
                "full_name": transcript_item.full_name,
                "gpa": float(transcript_item.gpa),
                "classification": transcript_item.classification,
                "match_status": transcript_item.match_status,
                "remark": transcript_item.remark,
            })
            
            progress = int(((idx + 1) / total) * 100)
            cache.set(f"import_progress_{import_id}", progress)
            
        summary_counts, summary_percent, total_cnt = build_summary(items)
        import_record.total_students = total_cnt
        import_record.summary_data = {
            "counts": summary_counts,
            "percentages": summary_percent,
            "valid": True,
            "class_match": True,
        }
        import_record.status = "IMPORTED"
        import_record.save(update_fields=["total_students", "summary_data", "status"])
        
        if user_id:
            try:
                AuditLog.objects.create(
                    user_id=user_id,
                    action="Import Transcript",
                    entity_name="TranscriptImport",
                    entity_id=import_record.id,
                    before_value="validated",
                    after_value="imported",
                )
            except Exception:
                pass
                
        cache.set(f"import_progress_{import_id}", 100)
        
    except Exception as exc:
        print("Import failed:", exc)
        try:
            import_record = TranscriptImport.objects.get(id=import_id)
            import_record.status = "FAILED"
            import_record.save(update_fields=["status"])
        except Exception:
            pass
        cache.set(f"import_progress_{import_id}", -1)


class TranscriptImportViewSet(viewsets.ModelViewSet):
    permission_classes = [AcademicAffairsOrAdminPermission]

    def get_queryset(self):
        return (
            TranscriptImport.objects.all()
            .select_related("uploaded_by", "class_info")
            .prefetch_related("items", "items__student")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TranscriptImportDetailSerializer
        return TranscriptImportListSerializer

    def create(self, request, *args, **kwargs):
        return Response(
            {"error": "Use /validate/ to create a transcript validation session and /import/ to confirm it."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_pdf(self, request):
        uploaded_file = request.FILES.get("file")
        class_id = request.data.get("class_id") or request.data.get("classId")
        school_year = (request.data.get("school_year") or request.data.get("schoolYear") or "").strip()
        semester = (request.data.get("semester") or "").strip() or None

        if not uploaded_file:
            return Response({"error": "File PDF is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file.name.lower().endswith(".pdf"):
            return Response({"error": "Only PDF files are supported."}, status=status.HTTP_400_BAD_REQUEST)
        if not class_id:
            return Response({"error": "class_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not school_year:
            return Response({"error": "school_year is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not semester:
            return Response({"error": "semester is required."}, status=status.HTTP_400_BAD_REQUEST)

        selected_class = ClassInfo.objects.filter(id=class_id).first()
        if not selected_class:
            return Response({"error": "Selected class was not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            import_record, result = validate_transcript_upload(
                uploaded_file=uploaded_file,
                class_info=selected_class,
                school_year=school_year,
                semester=semester,
                uploaded_by=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            if request.user and request.user.is_authenticated:
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action="Validate Transcript",
                        entity_name="TranscriptImport",
                        entity_id=None,
                        before_value="parse_pdf",
                        after_value="failed",
                    )
                except Exception:
                    pass
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        students = [
            {
                "student_db_id": item.get("student_db_id"),
                "student_id": item.get("student_id") or "",
                "student_code": item.get("student_code"),
                "full_name": item.get("full_name") or "",
                "gpa": float(item.get("gpa") or 0),
                "classification": item.get("classification") or "",
                "match_status": item.get("match_status") or "NOT_FOUND",
                "remark": item.get("remark") or "",
            }
            for item in result["students"]
        ]

        return Response(
            {
                "valid": result["valid"],
                "class_match": result["class_match"],
                "selected_class": result["selected_class"],
                "selected_class_id": result["selected_class_id"],
                "pdf_class": result["pdf_class"],
                "validation_session": import_record.id,
                "status": import_record.status,
                "students": students,
                "summary": result["summary"],
                "summary_percent": result["summary_percent"],
                "total_students": result["total_students"],
                "original_filename": result["original_filename"],
            }
        )

    @action(detail=False, methods=["post"], url_path="import")
    def import_pdf(self, request):
        validation_session = request.data.get("validation_session") or request.data.get("validationSession")
        if not validation_session:
            return Response({"error": "validation_session is required."}, status=status.HTTP_400_BAD_REQUEST)

        import_record = self.get_queryset().filter(id=validation_session).first()
        if not import_record:
            return Response({"error": "Validation session was not found."}, status=status.HTTP_404_NOT_FOUND)
        if import_record.status == "IMPORTED":
            return Response({"error": "This validation session has already been imported."}, status=status.HTTP_400_BAD_REQUEST)
        if not import_record.class_info:
            return Response({"error": "Selected class is missing for this validation session."}, status=status.HTTP_400_BAD_REQUEST)
        if import_record.pdf_class_name and import_record.class_info.name.strip().upper() != import_record.pdf_class_name.strip().upper():
            import_record.status = "FAILED"
            import_record.save(update_fields=["status"])
            return Response(
                {"error": f"PDF thuoc lop {import_record.pdf_class_name} nhung ban dang import vao lop {import_record.class_info.name}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        preview_data = import_record.preview_data or []
        if not preview_data:
            import_record.status = "FAILED"
            import_record.save(update_fields=["status"])
            return Response({"error": "Validation data is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize progress tracker in cache
        cache.set(f"import_progress_{validation_session}", 0)

        # Start asynchronous background thread
        user_id = request.user.id if request.user and request.user.is_authenticated else None
        thread = threading.Thread(target=process_import_async, args=(validation_session, user_id))
        thread.daemon = True
        thread.start()

        return Response(
            {
                "message": "Đang import...",
                "session_id": validation_session,
                "status": "PROCESSING",
            }
        )

    @action(detail=True, methods=["get"], url_path="stream")
    def stream_progress(self, request, pk=None):
        from django.http import StreamingHttpResponse

        def event_stream():
            import_id = pk
            last_progress = -2
            while True:
                progress = cache.get(f"import_progress_{import_id}")
                if progress is None:
                    progress = 0

                status_val = "PROCESSING"
                try:
                    import_record = TranscriptImport.objects.only("status").get(id=import_id)
                    status_val = import_record.status
                except Exception:
                    pass

                if progress != last_progress:
                    yield f"data: {{\"progress\": {progress}, \"status\": \"{status_val}\"}}\n\n"
                    last_progress = progress

                if progress >= 100 or status_val in ("IMPORTED", "FAILED") or progress == -1:
                    break

                time.sleep(0.1)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @action(detail=False, methods=["post"], url_path="import-attendance")
    def import_attendance(self, request):
        class_id = request.data.get("class_id") or request.data.get("classId")
        school_year = (request.data.get("school_year") or request.data.get("schoolYear") or "").strip()
        semester = (request.data.get("semester") or "").strip() or None
        student_attendances = request.data.get("student_attendances", [])

        if not class_id:
            return Response({"error": "class_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not school_year:
            return Response({"error": "school_year is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not semester:
            return Response({"error": "semester is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(student_attendances, list):
            return Response({"error": "student_attendances must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        selected_class = ClassInfo.objects.filter(id=class_id).first()
        if not selected_class:
            return Response({"error": "Selected class was not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            import_record, created = TranscriptImport.objects.get_or_create(
                class_info=selected_class,
                semester=semester,
                school_year=school_year,
                defaults={
                    "status": "IMPORTED",
                    "class_name": selected_class.name,
                    "original_filename": "Imported Attendance",
                }
            )
            # Ensure the status is set to IMPORTED if we are updating a draft/validated record
            if import_record.status != "IMPORTED":
                import_record.status = "IMPORTED"
                import_record.save(update_fields=["status"])

            success_count = 0
            failed_codes = []

            for item in student_attendances:
                student_code = str(item.get("student_code") or item.get("student_id") or "").strip()
                if not student_code:
                    continue
                try:
                    absent_sessions = int(item.get("absent_sessions") or item.get("absent") or 0)
                except (ValueError, TypeError):
                    absent_sessions = 0

                student = Student.objects.filter(student_id__iexact=student_code).first()
                
                import_item, item_created = TranscriptImportItem.objects.get_or_create(
                    transcript_import=import_record,
                    student_code=student_code,
                    defaults={
                        "student": student,
                        "full_name": student.full_name if student else "",
                        "gpa": 0.0,
                        "classification": "Trung bình",
                        "status": "MATCHED" if student else "NOT_FOUND",
                        "match_status": "MATCHED" if student else "NOT_FOUND",
                        "absent_sessions": absent_sessions,
                    }
                )
                if not item_created:
                    import_item.absent_sessions = absent_sessions
                    if student and not import_item.student:
                        import_item.student = student
                        import_item.status = "MATCHED"
                        import_item.match_status = "MATCHED"
                    import_item.save()
                
                success_count += 1

            # Recalculate summary data
            items = import_record.items.all()
            items_payload = []
            for item in items:
                items_payload.append({
                    "id": item.id,
                    "student": item.student.id if item.student else None,
                    "student_code": item.student_code,
                    "full_name": item.full_name,
                    "gpa": float(item.gpa),
                    "classification": item.classification,
                    "match_status": item.match_status,
                    "remark": item.remark,
                })
            summary_counts, summary_percent, total_cnt = build_summary(items_payload)
            import_record.total_students = total_cnt
            import_record.summary_data = {
                "counts": summary_counts,
                "percentages": summary_percent,
                "valid": True,
                "class_match": True,
            }
            import_record.save(update_fields=["total_students", "summary_data"])

        return Response({
            "message": f"Cập nhật số buổi vắng thành công cho {success_count} sinh viên.",
            "success_count": success_count,
            "failed_codes": failed_codes
        })
