from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from drl_app.models import (
    CriteriaSet,
    Criterion,
    Evaluation,
    GroupCriterion,
    Student,
    SubItem,
    User,
)


class CriteriaSetApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='secret',
            role='admin',
        )
        self.client.force_authenticate(self.admin)
        self.first_set = CriteriaSet.objects.create(
            name='Bộ HK1',
            semester='HK1',
            academic_year='2026-2027',
            is_active=True,
        )
        criterion = Criterion.objects.create(
            criteria_set=self.first_set,
            code='I',
            name='Học tập',
            max_score=20,
        )
        group = GroupCriterion.objects.create(criterion=criterion, name='Kết quả')
        SubItem.objects.create(group=group, name='Hoàn thành tốt', max_score=10)

    def test_clone_and_activate_criteria_set(self):
        response = self.client.post(reverse('criteria-set-list'), {
            'name': 'Bộ HK2',
            'semester': 'HK2',
            'academic_year': '2026-2027',
            'clone_from': self.first_set.id,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cloned_set = CriteriaSet.objects.get(pk=response.data['id'])
        self.assertEqual(cloned_set.criteria.count(), 1)
        self.assertEqual(
            cloned_set.criteria.first().groups.first().sub_items.count(),
            1,
        )

        activate_response = self.client.post(
            reverse('criteria-set-activate', args=(cloned_set.id,))
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.first_set.refresh_from_db()
        cloned_set.refresh_from_db()
        self.assertFalse(self.first_set.is_active)
        self.assertTrue(cloned_set.is_active)

    def test_default_criteria_list_only_returns_active_set(self):
        other_set = CriteriaSet.objects.create(name='Bộ nháp')
        Criterion.objects.create(
            criteria_set=other_set,
            code='I',
            name='Tiêu chí nháp',
            max_score=20,
        )

        response = self.client.get(reverse('criterion-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['criteria_set'], self.first_set.id)

    def test_evaluation_keeps_the_selected_set(self):
        student = Student.objects.create(
            student_id='SV001',
            full_name='Sinh viên',
            email='sv001@example.com',
            faculty='CNTT',
            cohort='2026',
        )
        sub_item = SubItem.objects.get(
            group__criterion__criteria_set=self.first_set
        )

        response = self.client.post(reverse('evaluation-list'), {
            'studentId': student.student_id,
            'semester': 'HK1',
            'year': '2026-2027',
            'scores': {str(sub_item.id): 10},
            'status': 'draft',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        evaluation = Evaluation.objects.get(student=student)
        self.assertEqual(evaluation.criteria_set, self.first_set)
        self.assertEqual(evaluation.total_score, 10)

    def test_surplus_repairs_previous_deficient_semester(self):
        student = Student.objects.create(
            student_id='SV002',
            full_name='Sinh viên bù kỳ trước',
            email='sv002@example.com',
            faculty='CNTT',
            cohort='2026',
        )
        sub_item = SubItem.objects.get(
            group__criterion__criteria_set=self.first_set
        )
        common = {
            'studentId': student.student_id,
            'year': '2026-2027',
            'criteriaSet': self.first_set.id,
            'status': 'draft',
        }
        first = self.client.post(reverse('evaluation-list'), {
            **common,
            'semester': 'HK1',
            'scores': {str(sub_item.id): 15},
            'rawScore': 15,
        }, format='json')
        second = self.client.post(reverse('evaluation-list'), {
            **common,
            'semester': 'HK2',
            'scores': {str(sub_item.id): 20},
            'rawScore': 25,
        }, format='json')

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        hk1 = Evaluation.objects.get(student=student, semester='HK1')
        hk2 = Evaluation.objects.get(student=student, semester='HK2')
        self.assertEqual(hk1.base_score, 15)
        self.assertEqual(hk1.carry_in, 5)
        self.assertEqual(hk1.total_score, 20)
        self.assertEqual(hk2.carry_out, 5)
        self.assertEqual(hk2.surplus_balance, 0)

    def test_surplus_waits_for_a_later_deficient_semester(self):
        student = Student.objects.create(
            student_id='SV003',
            full_name='Sinh viên chuyển kỳ sau',
            email='sv003@example.com',
            faculty='CNTT',
            cohort='2026',
        )
        sub_item = SubItem.objects.get(
            group__criterion__criteria_set=self.first_set
        )
        common = {
            'studentId': student.student_id,
            'year': '2026-2027',
            'criteriaSet': self.first_set.id,
            'status': 'draft',
        }
        for semester, score, raw_score in (
            ('HK1', 20, 20),
            ('HK2', 20, 25),
        ):
            response = self.client.post(reverse('evaluation-list'), {
                **common,
                'semester': semester,
                'scores': {str(sub_item.id): score},
                'rawScore': raw_score,
            }, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        hk2 = Evaluation.objects.get(student=student, semester='HK2')
        self.assertEqual(hk2.surplus_balance, 5)

        third = self.client.post(reverse('evaluation-list'), {
            **common,
            'semester': 'HK3',
            'scores': {str(sub_item.id): 15},
            'rawScore': 15,
        }, format='json')
        self.assertEqual(third.status_code, status.HTTP_201_CREATED)

        hk2.refresh_from_db()
        hk3 = Evaluation.objects.get(student=student, semester='HK3')
        self.assertEqual(hk2.carry_out, 5)
        self.assertEqual(hk2.surplus_balance, 0)
        self.assertEqual(hk3.carry_in, 5)
        self.assertEqual(hk3.total_score, 20)
