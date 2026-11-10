import os
import threading
from django import db
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from ...models import ReportDefinition, ReportJob
from ...services.workflow_guard import log_audit

from ..queries.evaluation_queries import EvaluationQueries
from ..queries.activity_queries import ActivityQueries
from ..exporters.excel_exporter import ExcelExporter
from ..exporters.pdf_exporter import PdfExporter

def check_report_permission(user, report_definition):
    """
    Validates user role against the report's permission requirements.
    """
    if not user.is_authenticated:
        return False
    if user.role == 'admin':
        return True
        
    required = report_definition.permission_required
    if required == 'student':
        return True
    elif required == 'class_monitor':
        return user.role in ('class_monitor', 'advisor', 'student_affairs', 'academic_affairs')
    elif required == 'advisor':
        return user.role in ('advisor', 'student_affairs', 'academic_affairs', 'class_monitor')
    elif required == 'student_affairs':
        return user.role in ('student_affairs', 'academic_affairs')
    elif required == 'academic_affairs':
        return user.role == 'academic_affairs'
        
    return False


def async_run_report_job(job_id):
    """
    Background worker task to compile queries and run exporters to produce report files.
    """
    db.close_old_connections()
    try:
        job = ReportJob.objects.get(id=job_id)
        job.status = 'RUNNING'
        job.started_at = timezone.now()
        job.save()

        code = job.report_definition.code
        parameters = job.parameters or {}

        # 1. Fetch data
        if code in ('evaluation_summary', 'evaluation_detail'):
            query_runner = EvaluationQueries()
            data = query_runner.execute(parameters)
        elif code == 'activity_summary':
            query_runner = ActivityQueries()
            data = query_runner.execute(parameters)
        elif code == 'audit_report':
            from drl_app.models import AuditLog
            audit_logs = AuditLog.objects.all().select_related('user').order_by('-created_at')
            data = []
            for log in audit_logs:
                data.append({
                    'created_at': log.created_at.strftime('%H:%M:%S %d/%m/%Y') if log.created_at else '',
                    'username': log.user.username if log.user else 'Hệ thống',
                    'role': log.user.role if log.user else '',
                    'action': log.action,
                    'entity_name': log.entity_name,
                    'before_value': log.before_value or '',
                    'after_value': log.after_value or '',
                    'ip_address': log.ip_address or '',
                })
        else:
            # Fallback or other reports return empty list for now
            data = []

        job.result_count = len(data)

        # 2. Exporter selection
        file_format = parameters.get('format', 'excel').lower()
        if file_format == 'pdf':
            exporter = PdfExporter()
            content = exporter.export(data, parameters)
            extension = 'pdf'
        else:
            exporter = ExcelExporter()
            content = exporter.export(data, parameters)
            extension = 'xlsx'

        # 3. Save generated file
        file_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(file_dir, exist_ok=True)

        file_name = f"report_{code}_{job.id}.{extension}"
        full_path = os.path.join(file_dir, file_name)

        with open(full_path, 'wb') as f:
            f.write(content)

        # 4. Success completion
        job.file_name = file_name
        job.file_path = f"{settings.MEDIA_URL}reports/{file_name}"
        job.status = 'SUCCESS'
        job.finished_at = timezone.now()
        job.save()

    except Exception as e:
        try:
            job = ReportJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.finished_at = timezone.now()
            job.save()
        except Exception:
            pass
    finally:
        db.close_old_connections()


def create_report_job(user, report_code, parameters, request=None):
    """
    Core service to check permissions, validate report definitions, create a ReportJob,
    and trigger its execution in a background thread.
    """
    report_def = get_object_or_404(ReportDefinition, code=report_code, is_active=True)
    
    # Permission validation
    if not check_report_permission(user, report_def):
        log_audit(
            user=user,
            action="Illegal Update Attempt",
            entity_name="ReportDefinition",
            entity_id=report_def.id,
            before_value=report_code,
            after_value="permission_denied",
            request=request
        )
        raise PermissionDenied("Bạn không có quyền yêu cầu xuất báo cáo này.")

    # Create ReportJob
    job = ReportJob.objects.create(
        report_definition=report_def,
        created_by=user,
        status='PENDING',
        parameters=parameters or {}
    )

    # Standard audit logging
    log_audit(
        user=user,
        action="Report Job Created",
        entity_name="ReportJob",
        entity_id=job.id,
        before_value="",
        after_value=f"code={report_code}",
        request=request
    )

    # Run execution in background thread
    threading.Thread(target=async_run_report_job, args=(job.id,), daemon=True).start()

    return job
