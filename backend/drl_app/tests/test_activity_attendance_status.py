from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from drl_app.models import (
    Activity,
    ActivityParticipant,
    CriteriaSet,
    Criterion,
    Student,
    User,
)


class ActivityAttendanceStatusTests(APITestCase):
    def setUp(self):
        criteria_set = CriteriaSet.objects.create(name='Bộ tiêu chí điểm danh')
        criterion = Criterion.objects.create(
            criteria_set=criteria_set,
            code='I',
            name='Hoạt động',
            max_score=20,
        )
        self.user = User.objects.create_user(
            username='attendance-student',
            password='secret',
            role='student',
            student_id='SV-ATTENDANCE',
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id='SV-ATTENDANCE',
            full_name='Sinh viên Điểm danh',
            email='attendance@example.com',
            faculty='CNTT',
            cohort='2024',
        )
        self.activity = Activity.objects.create(
            title='Hoạt động kiểm tra điểm danh',
            points=5,
            criterion=criterion,
            date=timezone.localdate(),
            start_time='00:00',
            end_time='23:59',
            duration_minutes=90,
            organizer='Đoàn Thanh Niên',
        )
        self.client.force_authenticate(self.user)

    def set_schedule(self, start_offset_minutes, end_offset_minutes):
        now = timezone.localtime(timezone.now())
        starts_at = now + timedelta(minutes=start_offset_minutes)
        ends_at = now + timedelta(minutes=end_offset_minutes)
        self.activity.date = starts_at.date()
        self.activity.start_time = starts_at.time().replace(microsecond=0)
        self.activity.end_time = ends_at.time().replace(microsecond=0)
        self.activity.save(update_fields=['date', 'start_time', 'end_time'])

    @patch('drl_app.views._verify_attendance_location')
    @patch('drl_app.views._verify_attendance_face')
    def test_check_in_only_keeps_registered_status(self, verify_face, verify_location):
        self.set_schedule(-10, 80)
        verify_face.return_value = (
            {'similarity': 1.0, 'liveness': 1.0, 'realness': 1.0},
            None,
        )
        verify_location.return_value = (
            {
                'latitude': 10.85,
                'longitude': 106.77,
                'accuracy': 5,
                'distance': 0,
            },
            None,
        )

        response = self.client.post(
            f'/api/activities/{self.activity.pk}/check-in/',
            {'deviceId': 'attendance-device'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        participant = ActivityParticipant.objects.get(
            activity=self.activity,
            student=self.student,
        )
        self.assertEqual(participant.status, 'registered')

    @patch('drl_app.views._verify_attendance_location')
    @patch('drl_app.views._verify_attendance_face')
    def test_check_out_opens_only_after_two_thirds(
        self,
        verify_face,
        verify_location,
    ):
        self.set_schedule(-10, 80)
        verify_face.return_value = (
            {'similarity': 1.0, 'liveness': 1.0, 'realness': 1.0},
            None,
        )
        verify_location.return_value = (
            {
                'latitude': 10.85,
                'longitude': 106.77,
                'accuracy': 5,
                'distance': 0,
            },
            None,
        )
        self.client.post(
            f'/api/activities/{self.activity.pk}/check-in/',
            {'deviceId': 'attendance-device'},
            format='json',
        )

        response = self.client.post(
            f'/api/activities/{self.activity.pk}/check-out/',
            {'deviceId': 'attendance-device'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ít nhất 2/3', response.data['error'])
        participant = ActivityParticipant.objects.get(
            activity=self.activity,
            student=self.student,
        )
        self.assertEqual(participant.status, 'registered')

    @patch('drl_app.views._verify_attendance_location')
    @patch('drl_app.views._verify_attendance_face')
    def test_check_out_after_two_thirds_marks_attended(
        self,
        verify_face,
        verify_location,
    ):
        self.set_schedule(-70, 20)
        verify_face.return_value = (
            {'similarity': 1.0, 'liveness': 1.0, 'realness': 1.0},
            None,
        )
        verify_location.return_value = (
            {
                'latitude': 10.85,
                'longitude': 106.77,
                'accuracy': 5,
                'distance': 0,
            },
            None,
        )
        self.client.post(
            f'/api/activities/{self.activity.pk}/check-in/',
            {'deviceId': 'attendance-device'},
            format='json',
        )

        response = self.client.post(
            f'/api/activities/{self.activity.pk}/check-out/',
            {'deviceId': 'attendance-device'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_completed'])
        self.assertGreaterEqual(response.data['completion_percent'], 2 / 3 * 100)
        participant = ActivityParticipant.objects.get(
            activity=self.activity,
            student=self.student,
        )
        self.assertEqual(participant.status, 'attended')
