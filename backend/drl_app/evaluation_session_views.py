from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Evaluation, EvaluationSession, Student
from .evaluation_session_serializers import EvaluationSessionSerializer
from .services.evaluation_session_service import SessionContext, heartbeat_session, start_session


def _resolve_context(request):
    evaluation_id = request.data.get('evaluationId') or request.data.get('evaluation_id')
    student_id = request.data.get('studentId') or request.data.get('student_id')
    semester = (request.data.get('semester') or '').strip()
    year = (request.data.get('year') or '').strip() or None

    evaluation = None
    student = None

    if evaluation_id:
        evaluation = get_object_or_404(Evaluation.objects.select_related('student'), pk=evaluation_id)
        student = evaluation.student
        semester = semester or evaluation.semester
        year = year or evaluation.year
    elif student_id:
        student = get_object_or_404(Student, student_id=student_id)
        if semester:
            evaluation = (
                Evaluation.objects.filter(student=student, semester=semester, year=year)
                .select_related('student')
                .first()
            )
    return SessionContext(evaluation=evaluation, student=student, semester=semester, year=year)


@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'evaluationId': openapi.Schema(type=openapi.TYPE_INTEGER),
            'studentId': openapi.Schema(type=openapi.TYPE_STRING),
            'semester': openapi.Schema(type=openapi.TYPE_STRING),
            'year': openapi.Schema(type=openapi.TYPE_STRING),
            'deviceInfo': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['semester'],
    ),
    responses={200: EvaluationSessionSerializer},
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def start_evaluation_session(request):
    context = _resolve_context(request)
    if not context.semester:
        return Response({'detail': 'semester is required.'}, status=status.HTTP_400_BAD_REQUEST)

    session, created = start_session(request=request, context=context)
    payload = EvaluationSessionSerializer(session).data
    payload['created'] = created
    return Response(payload, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_evaluation_session(request, pk: int):
    session = get_object_or_404(
        EvaluationSession.objects.select_related('evaluation__student', 'student'),
        pk=pk,
    )
    return Response(EvaluationSessionSerializer(session).data)


@api_view(['PATCH'])
@permission_classes([permissions.AllowAny])
def heartbeat_evaluation_session(request, pk: int):
    session = get_object_or_404(EvaluationSession.objects.select_related('evaluation__student', 'student'), pk=pk)
    session = heartbeat_session(request=request, session=session)
    return Response(EvaluationSessionSerializer(session).data)
