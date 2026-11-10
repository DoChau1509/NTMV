from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import PermissionDenied
from django.http import Http404
from ..models import ReportDefinition, ReportJob
from .serializers.report_serializers import ReportDefinitionSerializer, ReportJobSerializer
from .services.report_service import check_report_permission, create_report_job

class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ReportDefinitionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet to list and view active report definitions that the current user has permission to request.
    """
    serializer_class = ReportDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ReportDefinition.objects.filter(is_active=True)
        valid_ids = []
        for rd in queryset:
            if check_report_permission(user, rd):
                valid_ids.append(rd.id)
        return queryset.filter(id__in=valid_ids)


class ReportJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet to manage report export jobs. Standardizes creation, querying, and error formatting.
    """
    serializer_class = ReportJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        if user.role in ('admin', 'student_affairs', 'academic_affairs'):
            return ReportJob.objects.all()
        return ReportJob.objects.filter(created_by=user)

    def _error_res(self, code, message, details=None, status_code=400):
        return Response({
            'success': False,
            'code': code,
            'message': message,
            'details': details or {}
        }, status=status_code)

    def create(self, request, *args, **kwargs):
        report_code = request.data.get('report_code')
        parameters = request.data.get('parameters', {})

        if not report_code:
            return self._error_res('VALIDATION_ERROR', 'Trường report_code là bắt buộc.', {}, status.HTTP_400_BAD_REQUEST)

        try:
            job = create_report_job(
                user=request.user,
                report_code=report_code,
                parameters=parameters,
                request=request
            )
            return Response({
                'job_id': job.id,
                'status': job.status
            }, status=status.HTTP_201_CREATED)
        except PermissionDenied as e:
            return self._error_res('UNAUTHORIZED', str(e), {}, status.HTTP_403_FORBIDDEN)
        except Http404:
            return self._error_res('NOT_FOUND', 'Không tìm thấy loại báo cáo yêu cầu.', {}, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return self._error_res('SERVER_ERROR', str(e), {}, status.HTTP_500_INTERNAL_SERVER_ERROR)
