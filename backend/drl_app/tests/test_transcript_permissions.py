from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from drl_app.transcript_views import AcademicAffairsOrAdminPermission


class TranscriptPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = AcademicAffairsOrAdminPermission()

    def request_for(self, method, role):
        request = getattr(self.factory, method)("/api/transcripts/")
        request.user = SimpleNamespace(is_authenticated=True, role=role)
        return request

    def test_student_affairs_can_read_imported_transcripts(self):
        request = self.request_for("get", "student_affairs")

        self.assertTrue(self.permission.has_permission(request, None))

    def test_student_affairs_cannot_create_transcript_import(self):
        request = self.request_for("post", "student_affairs")

        self.assertFalse(self.permission.has_permission(request, None))

    def test_academic_affairs_can_create_transcript_import(self):
        request = self.request_for("post", "academic_affairs")

        self.assertTrue(self.permission.has_permission(request, None))
