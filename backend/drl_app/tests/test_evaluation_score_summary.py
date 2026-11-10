from rest_framework import status
from rest_framework.test import APITestCase

from drl_app.models import (
    CriteriaSet,
    Criterion,
    Evaluation,
    Student,
    User,
)


class EvaluationScoreSummaryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='score-history-student',
            password='secret',
            role='student',
            student_id='SV-HISTORY',
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id='SV-HISTORY',
            full_name='Sinh viên Lịch sử',
            email='score-history@example.com',
            faculty='CNTT',
            cohort='2024',
        )
        self.criteria_set = CriteriaSet.objects.create(
            name='Bộ tiêu chí 100 điểm',
            semester='HK1',
            academic_year='2025-2026',
        )
        Criterion.objects.create(
            criteria_set=self.criteria_set,
            code='I',
            name='Ý thức học tập',
            max_score=40,
        )
        Criterion.objects.create(
            criteria_set=self.criteria_set,
            code='II',
            name='Hoạt động phong trào',
            max_score=60,
        )
        Evaluation.objects.create(
            student=self.student,
            criteria_set=self.criteria_set,
            semester='HK1',
            year='2025-2026',
            raw_score=72,
            base_score=72,
            total_score=72,
            classification='Khá',
            status='approved',
        )
        Evaluation.objects.create(
            student=self.student,
            criteria_set=self.criteria_set,
            semester='HK2',
            year='2025-2026',
            raw_score=110,
            base_score=100,
            surplus_balance=10,
            total_score=100,
            classification='Xuất sắc',
            status='approved',
        )
        self.client.force_authenticate(self.user)

    def test_evaluation_history_includes_missing_and_complete_points(self):
        response = self.client.get(
            f'/api/evaluations/?studentId={self.student.student_id}',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_semester = {item['semester']: item for item in response.data}

        first_semester = by_semester['HK1']
        self.assertEqual(first_semester['maximum_score'], 100)
        self.assertEqual(first_semester['points_missing'], 28)
        self.assertEqual(first_semester['points_excess'], 0)
        self.assertFalse(first_semester['is_score_complete'])

        second_semester = by_semester['HK2']
        self.assertEqual(second_semester['maximum_score'], 100)
        self.assertEqual(second_semester['points_missing'], 0)
        self.assertEqual(second_semester['points_excess'], 10)
        self.assertTrue(second_semester['is_score_complete'])
