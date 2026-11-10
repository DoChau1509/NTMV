from rest_framework import status
from rest_framework.test import APITestCase

from drl_app.models import Activity, CriteriaSet, Criterion, Organization


class OrganizationTests(APITestCase):
    def test_create_update_and_list_organization(self):
        create_response = self.client.post(
            '/api/organizations/',
            {'name': '  Đoàn Thanh Niên  ', 'type': 'Đoàn - Hội'},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        organization_id = create_response.data['id']
        self.assertEqual(create_response.data['name'], 'Đoàn Thanh Niên')
        self.assertEqual(create_response.data['member_count'], 0)
        self.assertEqual(create_response.data['activity_count'], 0)

        criteria_set = CriteriaSet.objects.create(name='Bộ tiêu chí đơn vị')
        criterion = Criterion.objects.create(
            criteria_set=criteria_set,
            code='I',
            name='Hoạt động',
            max_score=20,
        )
        activity = Activity.objects.create(
            title='Hoạt động của đơn vị',
            points=5,
            criterion=criterion,
            date='2026-07-04',
            organizer='Đoàn Thanh Niên',
        )

        update_response = self.client.patch(
            f'/api/organizations/{organization_id}/',
            {'name': 'Đoàn Thanh Niên ITC', 'type': 'Phòng/Ban'},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['type'], 'Phòng/Ban')
        activity.refresh_from_db()
        self.assertEqual(activity.organizer, 'Đoàn Thanh Niên ITC')

        delete_response = self.client.delete(
            f'/api/organizations/{organization_id}/',
        )
        self.assertEqual(delete_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_organization_name_is_unique_case_insensitively(self):
        Organization.objects.create(name='Quận đoàn 9', type='Đơn vị ngoài trường')

        response = self.client.post(
            '/api/organizations/',
            {'name': 'quận ĐOÀN 9', 'type': 'Đơn vị ngoài trường'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
