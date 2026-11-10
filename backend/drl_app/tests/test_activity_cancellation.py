from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from drl_app.models import (
    Activity,
    ActivityCheckIn,
    ActivityParticipant,
    CriteriaSet,
    Criterion,
    Student,
    User,
)


class ActivityCancellationTests(APITestCase):
    def setUp(self):
        criteria_set = CriteriaSet.objects.create(name='Bộ tiêu chí hủy đăng ký')
        criterion = Criterion.objects.create(
            criteria_set=criteria_set,
            code='I',
            name='Hoạt động',
            max_score=20,
        )
        self.user = User.objects.create_user(
            username='cancel-student',
            password='secret',
            role='student',
            student_id='SV-CANCEL',
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id='SV-CANCEL',
            full_name='Sinh viên Hủy',
            email='cancel@example.com',
            faculty='CNTT',
            cohort='2024',
        )
        starts_at = timezone.localtime(timezone.now()) + timedelta(hours=48)
        self.activity = Activity.objects.create(
            title='Hoạt động cho phép hủy',
            points=5,
            criterion=criterion,
            date=starts_at.date(),
            start_time=starts_at.time().replace(microsecond=0),
            organizer='Đoàn Thanh Niên',
        )
        self.participant = ActivityParticipant.objects.create(
            activity=self.activity,
            student=self.student,
        )
        self.url = (
            f'/api/activities/{self.activity.pk}/cancel-registration/'
        )
        self.client.force_authenticate(self.user)

    def test_student_can_cancel_more_than_24_hours_before_activity(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ActivityParticipant.objects.filter(pk=self.participant.pk).exists(),
        )
        self.assertEqual(response.data['message'], 'Hủy đăng ký hoạt động thành công.')

    def test_student_cannot_cancel_within_24_hours(self):
        starts_at = timezone.localtime(timezone.now()) + timedelta(hours=23)
        self.activity.date = starts_at.date()
        self.activity.start_time = starts_at.time().replace(microsecond=0)
        self.activity.save(update_fields=['date', 'start_time'])

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            ActivityParticipant.objects.filter(pk=self.participant.pk).exists(),
        )
        self.assertIn('ít nhất 24 giờ', response.data['error'])

    def test_student_cannot_cancel_after_check_in(self):
        ActivityCheckIn.objects.create(
            activity=self.activity,
            student=self.student,
            latitude=10.85,
            longitude=106.77,
            device_id='cancel-device',
            ip_address='127.0.0.1',
        )

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error'],
            'Không thể hủy đăng ký sau khi đã check-in.',
        )
