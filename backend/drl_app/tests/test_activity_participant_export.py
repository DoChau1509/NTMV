from datetime import datetime
from io import BytesIO

import openpyxl
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from drl_app.models import (
    Activity,
    ActivityCheckIn,
    ActivityCheckOut,
    ActivityParticipant,
    CriteriaSet,
    Criterion,
    Student,
    User,
)


class ActivityParticipantExportTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin-export',
            password='secret',
            role='admin',
            full_name='Quản trị viên',
        )
        self.student_user = User.objects.create_user(
            username='student-export',
            password='secret',
            role='student',
            full_name='Nguyễn Văn An',
            student_id='SV001',
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='SV001',
            full_name='Nguyễn Văn An',
            email='sv001@example.com',
            faculty='Công nghệ thông tin',
            cohort='2024',
        )
        criteria_set = CriteriaSet.objects.create(name='Bộ tiêu chí kiểm thử')
        criterion = Criterion.objects.create(
            criteria_set=criteria_set,
            code='I',
            name='Hoạt động',
            max_score=20,
        )
        self.activity = Activity.objects.create(
            title='Ngày hội sinh viên',
            points=5,
            criterion=criterion,
            date='2026-07-03',
            organizer='Đoàn Thanh Niên',
        )
        ActivityParticipant.objects.create(
            activity=self.activity,
            student=self.student,
        )

        checkin = ActivityCheckIn.objects.create(
            activity=self.activity,
            student=self.student,
            latitude=10.85,
            longitude=106.77,
            device_id='test-device',
            ip_address='127.0.0.1',
        )
        checkout = ActivityCheckOut.objects.create(
            activity=self.activity,
            student=self.student,
            latitude=10.85,
            longitude=106.77,
            device_id='test-device',
            ip_address='127.0.0.1',
        )
        self.checkin_time = timezone.make_aware(datetime(2026, 7, 3, 8, 15))
        self.checkout_time = timezone.make_aware(datetime(2026, 7, 3, 11, 30))
        ActivityCheckIn.objects.filter(pk=checkin.pk).update(
            check_in_time=self.checkin_time,
        )
        ActivityCheckOut.objects.filter(pk=checkout.pk).update(
            check_out_time=self.checkout_time,
        )
        self.url = f'/api/activities/{self.activity.pk}/export-participants/'

    def test_admin_can_export_participants_as_excel(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn(
            f'activity_{self.activity.pk}_participants.xlsx',
            response['Content-Disposition'],
        )

        workbook = openpyxl.load_workbook(BytesIO(response.content))
        sheet = workbook['Danh sách tham gia']
        self.assertEqual(
            [cell.value for cell in sheet[1]],
            [
                'Mã sinh viên',
                'Họ và tên',
                'Thời gian check-in',
                'Thời gian check-out',
                'Trạng thái',
            ],
        )
        self.assertEqual(sheet['A2'].value, 'SV001')
        self.assertEqual(sheet['B2'].value, 'Nguyễn Văn An')
        self.assertEqual(sheet['C2'].value, datetime(2026, 7, 3, 8, 15))
        self.assertEqual(sheet['D2'].value, datetime(2026, 7, 3, 11, 30))
        self.assertEqual(sheet['E2'].value, 'Đã đăng ký')

    def test_student_cannot_export_participant_list(self):
        self.client.force_authenticate(self.student_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
