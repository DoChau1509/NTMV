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


class ActivityCapacityTests(APITestCase):
    def setUp(self):
        criteria_set = CriteriaSet.objects.create(name='Bộ tiêu chí sức chứa')
        criterion = Criterion.objects.create(
            criteria_set=criteria_set,
            code='I',
            name='Hoạt động',
            max_score=20,
        )
        self.activity = Activity.objects.create(
            title='Hoạt động giới hạn',
            points=5,
            criterion=criterion,
            date='2026-07-03',
            organizer='Đoàn Thanh Niên',
            max_participants=1,
        )
        self.first_user = User.objects.create_user(
            username='capacity-first',
            password='secret',
            role='student',
            student_id='SV001',
        )
        self.first_student = Student.objects.create(
            user=self.first_user,
            student_id='SV001',
            full_name='Sinh viên Một',
            email='capacity-first@example.com',
            faculty='CNTT',
            cohort='2024',
        )
        self.second_user = User.objects.create_user(
            username='capacity-second',
            password='secret',
            role='student',
            student_id='SV002',
        )
        self.second_student = Student.objects.create(
            user=self.second_user,
            student_id='SV002',
            full_name='Sinh viên Hai',
            email='capacity-second@example.com',
            faculty='CNTT',
            cohort='2024',
        )
        self.register_url = f'/api/activities/{self.activity.pk}/register/'

    def test_registration_is_rejected_after_capacity_is_reached(self):
        first_response = self.client.post(
            self.register_url,
            {'studentId': self.first_student.student_id},
            format='json',
        )
        second_response = self.client.post(
            self.register_url,
            {'studentId': self.second_student.student_id},
            format='json',
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            second_response.data['error'],
            'Hoạt động đã đủ số lượng người tham gia tối đa.',
        )
        self.assertEqual(self.activity.participants.count(), 1)

    def test_existing_participant_can_register_again_when_activity_is_full(self):
        ActivityParticipant.objects.create(
            activity=self.activity,
            student=self.first_student,
        )

        response = self.client.post(
            self.register_url,
            {'studentId': self.first_student.student_id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.activity.participants.count(), 1)

    def test_direct_check_in_is_rejected_before_face_scan_when_full(self):
        ActivityParticipant.objects.create(
            activity=self.activity,
            student=self.first_student,
        )
        self.client.force_authenticate(self.second_user)

        response = self.client.post(
            f'/api/activities/{self.activity.pk}/check-in/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error'],
            'Hoạt động đã đủ số lượng người tham gia tối đa.',
        )

    def test_maximum_cannot_be_reduced_below_registered_count(self):
        self.activity.max_participants = 2
        self.activity.save(update_fields=['max_participants'])
        ActivityParticipant.objects.create(
            activity=self.activity,
            student=self.first_student,
        )
        ActivityParticipant.objects.create(
            activity=self.activity,
            student=self.second_student,
        )

        response = self.client.patch(
            f'/api/activities/{self.activity.pk}/',
            {'max_participants': 1},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('max_participants', response.data)

    def test_maximum_can_be_updated(self):
        response = self.client.patch(
            f'/api/activities/{self.activity.pk}/',
            {'max_participants': 250},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.max_participants, 250)
