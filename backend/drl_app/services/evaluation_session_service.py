from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from ..models import AuditLog, Evaluation, EvaluationSession, Student


@dataclass
class SessionContext:
    evaluation: Evaluation | None = None
    student: Student | None = None
    semester: str = ''
    year: str | None = None


def _get_ip_address(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_device_info(request) -> str:
    header_device = request.META.get('HTTP_X_DEVICE_INFO') or request.META.get('HTTP_X_DEVICE_ID')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    parts = [part for part in [header_device, user_agent] if part]
    return ' | '.join(parts)


def _audit(session: EvaluationSession, user, action: str, before_value: str = '', after_value: str = '') -> None:
    try:
        AuditLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action=action,
            entity_name='EvaluationSession',
            entity_id=session.id,
            before_value=before_value or None,
            after_value=after_value or None,
            ip_address=session.ip_address,
            device_id=session.device_info[:255] or None,
        )
    except Exception:
        pass


def _build_lookup(context: SessionContext, device_info: str, ip_address: str | None) -> dict:
    lookup: dict = {}
    if context.evaluation:
        lookup['evaluation'] = context.evaluation
    if context.student:
        lookup['student'] = context.student
    if context.semester:
        lookup['semester'] = context.semester
    if context.year:
        lookup['year'] = context.year
    if not lookup:
        if context.semester:
            lookup['semester'] = context.semester
        if context.year:
            lookup['year'] = context.year
        if device_info:
            lookup['device_info'] = device_info
        if ip_address:
            lookup['ip_address'] = ip_address
    return lookup


@transaction.atomic
def start_session(*, request, context: SessionContext) -> tuple[EvaluationSession, bool]:
    device_info = _get_device_info(request)
    ip_address = _get_ip_address(request)
    lookup = _build_lookup(context, device_info, ip_address)
    defaults = {
        'status': 'active',
        'last_active': timezone.now(),
        'device_info': device_info,
        'ip_address': ip_address,
    }
    session, created = EvaluationSession.objects.get_or_create(defaults=defaults, **lookup)
    if not created:
        before_status = session.status
        session.status = 'active'
        session.last_active = timezone.now()
        if context.evaluation and not session.evaluation_id:
            session.evaluation = context.evaluation
        if context.student and not session.student_id:
            session.student = context.student
        if context.semester and not session.semester:
            session.semester = context.semester
        if context.year and not session.year:
            session.year = context.year
        if device_info:
            session.device_info = device_info
        if ip_address:
            session.ip_address = ip_address
        session.save()
        _audit(session, getattr(request, 'user', None), 'Evaluation Session Resumed', before_value=before_status, after_value='active')
        return session, False

    _audit(session, getattr(request, 'user', None), 'Evaluation Session Started', after_value='active')
    return session, True


@transaction.atomic
def heartbeat_session(*, request, session: EvaluationSession) -> EvaluationSession:
    session.last_active = timezone.now()
    if session.status != 'active':
        session.status = 'active'
    device_info = _get_device_info(request)
    ip_address = _get_ip_address(request)
    if device_info:
        session.device_info = device_info
    if ip_address:
        session.ip_address = ip_address
    session.save()
    return session
