import json
from datetime import date
from unittest.mock import patch

from django.test import Client, TestCase

from .models import Gathering, GatheringItem, GatheringOrder, OrderAccount


class GatheringTests(TestCase):
    def setUp(self):
        self.admin = self.account('admin')
        self.staff = self.account('employee')
        self.guest = Client()
        self.batch = self.request(self.staff, 'post', 'gatherings/', {
            'name': 'Gom tháng 11', 'startsOn': '2026-11-01', 'endsOn': '2026-11-30',
        }).json()
        self.payload = {
            'customerName': 'Nguyễn An', 'profileUrl': 'https://example.com/an', 'paidAmount': 100000,
            'items': [self.item(), self.item(name='Túi', quantity=3, unitPrice='0.10', depositDueOn=None)],
        }

    def account(self, role):
        account = OrderAccount.objects.create(username=role, full_name=role, role=role, password='unused')
        client = Client()
        session = client.session
        session['order_account_id'] = account.pk
        session.save()
        return client

    def item(self, **changes):
        return {'name': 'Áo', 'quantity': 2, 'unitPrice': '12.35',
                'depositDueOn': '2026-11-07', 'status': 'bought', **changes}

    def request(self, client, method, path, data=None):
        return getattr(client, method)('/api/order/' + path, data=json.dumps(data) if data is not None else '', content_type='application/json')

    def create_order(self, payload=None):
        return self.request(self.staff, 'post', f"gatherings/{self.batch['id']}/orders/", payload or self.payload)

    def test_guests_cannot_read_or_write_any_gathering_endpoint(self):
        order = self.create_order().json()
        for method, path, payload in [
            ('get', 'gatherings/', None), ('post', 'gatherings/', {}),
            ('put', f"gatherings/{self.batch['id']}/", {}), ('delete', f"gatherings/{self.batch['id']}/", None),
            ('post', f"gatherings/{self.batch['id']}/orders/", self.payload),
            ('put', f"gathering-orders/{order['id']}/", self.payload), ('delete', f"gathering-orders/{order['id']}/", None),
        ]:
            self.assertEqual(self.request(self.guest, method, path, payload).status_code, 401)
        account = OrderAccount.objects.get(username='employee')
        account.delete()
        self.assertEqual(self.staff.get('/api/order/gatherings/').status_code, 401)

    def test_exact_totals_persistence_and_both_staff_and_admin_can_edit(self):
        response = self.create_order({**self.payload, 'items': [
            self.item(note='Màu xanh\nSize M'), self.payload['items'][1],
        ]})
        self.assertEqual(response.status_code, 201)
        order = response.json()
        self.assertEqual(order['totalCny'], '25.00')
        self.assertEqual(order['items'][0]['totalCny'], '24.70')
        self.assertEqual(order['paidAmount'], 100000)
        self.assertEqual(order['items'][0]['note'], 'Màu xanh\nSize M')
        self.assertEqual(order['items'][1]['note'], '')
        self.assertIsNone(order['items'][1]['depositDueOn'])
        nested = self.admin.get('/api/order/gatherings/').json()['items'][0]['orders'][0]
        self.assertEqual(nested, order)
        edited = {**order, 'customerName': 'Tên mới', 'paidAmount': 200000}
        edited['items'][0].update(quantity=4, status='arrived', depositDueOn=None, note='Size L')
        saved = self.request(self.admin, 'put', f"gathering-orders/{order['id']}/", edited).json()
        self.assertEqual(saved['totalCny'], '49.70')
        self.assertEqual(saved['items'][0]['id'], order['items'][0]['id'])
        self.assertIsNone(saved['items'][0]['depositDueOn'])
        self.assertEqual(saved['items'][0]['status'], 'arrived')
        self.assertEqual(saved['paidAmount'], 200000)
        self.assertEqual(saved['items'][0]['note'], 'Size L')
        stored = GatheringItem.objects.get(pk=saved['items'][0]['id'])
        self.assertEqual(stored.note, 'Size L')
        del edited['items'][0]['note']
        preserved = self.request(self.admin, 'put', f"gathering-orders/{order['id']}/", edited).json()
        self.assertEqual(preserved['items'][0]['note'], 'Size L')
        edited['items'][0]['note'] = ''
        cleared = self.request(self.admin, 'put', f"gathering-orders/{order['id']}/", edited).json()
        self.assertEqual(cleared['items'][0]['note'], '')

    def test_not_bought_status_persists_and_can_change_to_bought(self):
        response = self.create_order({**self.payload, 'items': [self.item(status='not_bought')]})
        self.assertEqual(response.status_code, 201)
        order = response.json()
        self.assertEqual(order['items'][0]['status'], 'not_bought')
        stored = GatheringItem.objects.get(pk=order['items'][0]['id'])
        stored.full_clean()
        self.assertEqual(stored.status, 'not_bought')
        nested = self.admin.get('/api/order/gatherings/').json()['items'][0]['orders'][0]
        self.assertEqual(nested['items'][0]['status'], 'not_bought')
        for status in ['bought', 'not_bought']:
            order['items'][0]['status'] = status
            saved = self.request(self.admin, 'put', f"gathering-orders/{order['id']}/", order)
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()['items'][0]['status'], status)
            stored.refresh_from_db()
            self.assertEqual(stored.status, status)

    def test_manual_vnd_prices_discount_and_legacy_client_preservation(self):
        payload = {**self.payload, 'discountAmount': 25000, 'items': [
            self.item(unitPriceVnd=100000), self.item(name='Túi', quantity=3, unitPriceVnd=50000),
        ]}
        response = self.create_order(payload)
        self.assertEqual(response.status_code, 201)
        order = response.json()
        self.assertEqual(order['subtotalVnd'], '350000')
        self.assertEqual(order['totalVnd'], '325000')
        self.assertEqual(order['discountAmount'], 25000)
        self.assertEqual(order['items'][0]['unitPriceVnd'], 100000)
        nested = self.admin.get('/api/order/gatherings/').json()['items'][0]['orders'][0]
        self.assertEqual(nested, order)
        path = f"gathering-orders/{order['id']}/"
        legacy = {**order, 'items': [{k: v for k, v in row.items() if k != 'unitPriceVnd'} for row in order['items']]}
        del legacy['discountAmount']
        saved = self.request(self.admin, 'put', path, legacy).json()
        self.assertEqual(saved['totalVnd'], '325000')
        for discount in [0, 350000]:
            saved = self.request(self.admin, 'put', path, {**order, 'discountAmount': discount}).json()
            self.assertEqual(saved['totalVnd'], str(350000 - discount))
            self.assertEqual(GatheringOrder.objects.get(pk=order['id']).discount_amount, discount)

    def test_unknown_zero_and_large_vnd_prices(self):
        unknown = self.create_order().json()
        self.assertIsNone(unknown['items'][0]['unitPriceVnd'])
        self.assertIsNone(unknown['totalVnd'])
        self.assertEqual(unknown['discountAmount'], 0)
        zero = self.create_order({**self.payload, 'items': [self.item(unitPriceVnd=0)]}).json()
        self.assertEqual(zero['totalVnd'], '0')
        large = self.create_order({**self.payload, 'discountAmount': 1, 'items': [
            self.item(quantity=1000000, unitPriceVnd=1000000000000), self.item(quantity=1, unitPriceVnd=3),
        ]}).json()
        self.assertEqual(large['totalVnd'], '1000000000000000002')
        path = f"gathering-orders/{zero['id']}/"
        cleared = self.request(self.admin, 'put', path, {**zero, 'items': [{**zero['items'][0], 'unitPriceVnd': None}]}).json()
        self.assertIsNone(cleared['subtotalVnd'])
        self.assertIsNone(cleared['totalVnd'])

    def test_invalid_vnd_prices_and_discounts_do_not_partially_save(self):
        payload = {**self.payload, 'discountAmount': 10000, 'items': [self.item(unitPriceVnd=100000)]}
        order = self.create_order(payload).json()
        invalid_payloads = [
            {**payload, 'items': [self.item(unitPriceVnd=value)]}
            for value in [-1, True, 1.5, '100000', '', 1000000000001]
        ] + [{**payload, 'discountAmount': value} for value in [-1, True, 1.5, '10000', None, '', 1000000000001, 200001]]
        for bad in invalid_payloads:
            with self.subTest(bad=bad):
                bad['customerName'] = 'Must not save'
                self.assertEqual(self.create_order(bad).status_code, 400)
                self.assertEqual(self.request(self.admin, 'put', f"gathering-orders/{order['id']}/", bad).status_code, 400)
                stored = GatheringOrder.objects.get(pk=order['id'])
                self.assertEqual(stored.customer_name, 'Nguyễn An')
                self.assertEqual(stored.discount_amount, 10000)
                self.assertEqual(stored.items.get().unit_price_vnd, 100000)
        self.assertEqual(GatheringOrder.objects.count(), 1)

    def test_one_day_reminders_overdue_and_cleared_payment(self):
        with patch('order_app.gathering_views.timezone.localdate', return_value=date(2026, 11, 6)):
            for due, paid, expected in [
                ('2026-11-08', 0, None), ('2026-11-07', 100000, 'due_soon'),
                ('2026-11-06', 100000, 'due_soon'), ('2026-11-05', 100000, 'overdue'),
                ('2026-11-05', 200000, None), ('2026-11-05', 250000, None), (None, 0, None),
            ]:
                response = self.create_order({**self.payload, 'paidAmount': paid, 'items': [self.item(depositDueOn=due, unitPriceVnd=100000)]})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()['items'][0]['deadlineAlert'], expected)
                self.assertNotIn('paymentStatus', response.json()['items'][0])

    def test_remaining_amount_is_calculated_and_ignores_old_manual_zero(self):
        payload = {**self.payload, 'discountAmount': 25000, 'remainingAmount': 0,
                   'items': [self.item(unitPriceVnd=100000, quantity=3)]}
        created = self.create_order(payload).json()
        self.assertEqual(created['remainingAmount'], '175000')
        GatheringOrder.objects.filter(pk=created['id']).update(remaining_amount=0)
        nested = self.admin.get('/api/order/gatherings/').json()['items'][0]['orders'][0]
        self.assertEqual(nested['remainingAmount'], '175000')
        path = f"gathering-orders/{created['id']}/"
        for paid, expected in [(0, '275000'), (200000, '75000'), (275000, '0'), (300000, '0')]:
            response = self.request(self.staff, 'put', path, {**created, 'paidAmount': paid, 'remainingAmount': 0})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['remainingAmount'], expected)
        updated = {**created, 'paidAmount': 50000, 'discountAmount': 10000,
                   'items': [{**created['items'][0], 'quantity': 2, 'unitPriceVnd': 80000}]}
        self.assertEqual(self.request(self.staff, 'put', path, updated).json()['remainingAmount'], '100000')

    def test_remaining_amount_distinguishes_unknown_zero_and_large_balances(self):
        self.assertIsNone(self.create_order({**self.payload, 'remainingAmount': 0}).json()['remainingAmount'])
        free = self.create_order({**self.payload, 'paidAmount': 0, 'items': [self.item(unitPriceVnd=0)]}).json()
        self.assertEqual(free['remainingAmount'], '0')
        large = self.create_order({**self.payload, 'paidAmount': 2, 'discountAmount': 1,
                                   'items': [self.item(quantity=1000000, unitPriceVnd=1000000000000)]}).json()
        self.assertEqual(large['remainingAmount'], '999999999999999997')
        mixed = self.create_order({**self.payload, 'items': [self.item(unitPriceVnd=100000), self.item()]}).json()
        self.assertIsNone(mixed['remainingAmount'])

    def test_invalid_data_does_not_partially_change_customer_or_items(self):
        order = self.create_order().json()
        for bad in [
            {'quantity': 0}, {'quantity': True}, {'quantity': 1.5}, {'unitPrice': 'NaN'},
            {'unitPrice': 'Infinity'}, {'unitPrice': '-1'}, {'unitPrice': '1.001'}, {'unitPrice': True},
            {'unitPrice': '10000000000'}, {'status': 'bad'},
            {'depositDueOn': False}, {'depositDueOn': '2026-02-30'}, {'name': '   '},
            {'note': None}, {'note': 123}, {'note': 'x' * 2001},
        ]:
            with self.subTest(bad=bad):
                payload = {**self.payload, 'customerName': 'Must not save', 'items': [self.item(), self.item(**bad)]}
                self.assertEqual(self.request(self.admin, 'put', f"gathering-orders/{order['id']}/", payload).status_code, 400)
                self.assertEqual(GatheringOrder.objects.get(pk=order['id']).customer_name, 'Nguyễn An')
                self.assertEqual(GatheringItem.objects.count(), 2)
        for bad in [{'items': []}, {'paidAmount': -1}, {'paidAmount': 1.5}, {'paidAmount': True},
                    {'profileUrl': 'javascript:alert(1)'}, {'profileUrl': 'ftp://example.com'}]:
            self.assertEqual(self.create_order({**self.payload, **bad}).status_code, 400)

    def test_item_ids_cannot_be_taken_from_another_order_or_duplicated(self):
        first, other = self.create_order().json(), self.create_order().json()
        path = f"gathering-orders/{first['id']}/"
        self.assertEqual(self.request(self.staff, 'put', path, {**first, 'items': other['items']}).status_code, 400)
        self.assertEqual(self.request(self.staff, 'put', path, {**first, 'items': [first['items'][0]] * 2}).status_code, 400)
        payload = {**first, 'items': [first['items'][0], self.item(name='Mới')]}
        updated = self.request(self.staff, 'put', path, payload).json()
        self.assertEqual(len(updated['items']), 2)
        self.assertEqual(updated['items'][0]['id'], first['items'][0]['id'])
        self.assertFalse(GatheringItem.objects.filter(pk=first['items'][1]['id']).exists())
        self.assertEqual(GatheringOrder.objects.get(pk=other['id']).items.count(), 2)

    def test_batch_dates_edit_and_safe_delete(self):
        path = f"gatherings/{self.batch['id']}/"
        self.assertEqual(self.request(self.staff, 'put', path, {**self.batch, 'endsOn': '2026-10-01'}).status_code, 400)
        edited = self.request(self.admin, 'put', path, {**self.batch, 'name': 'Gom mới'})
        self.assertEqual(edited.json()['name'], 'Gom mới')
        order = self.create_order().json()
        self.assertEqual(self.request(self.staff, 'delete', path).status_code, 409)
        self.assertEqual(self.request(self.admin, 'delete', f"gathering-orders/{order['id']}/").status_code, 200)
        self.assertEqual(GatheringItem.objects.count(), 0)
        self.assertEqual(self.request(self.staff, 'delete', path).status_code, 200)
        self.assertEqual(Gathering.objects.count(), 0)
        for method, path, payload in [('put', 'gatherings/999/', {}), ('post', 'gatherings/999/orders/', self.payload), ('delete', 'gathering-orders/999/', None)]:
            self.assertEqual(self.request(self.staff, method, path, payload).status_code, 404)

    def test_csrf_is_required_for_staff_writes(self):
        secure = Client(enforce_csrf_checks=True)
        secure.cookies = self.staff.cookies
        self.assertEqual(self.request(secure, 'post', f"gatherings/{self.batch['id']}/orders/", self.payload).status_code, 403)
