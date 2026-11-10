import json
from unittest.mock import patch
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from .models import OrderAccount, Shipment, OrderPricing, default_pricing


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OrderPermissionsTests(TestCase):
    def test_excel_export_matches_filters_and_preserves_money_and_text(self):
        from datetime import datetime, timezone
        from io import BytesIO
        from openpyxl import load_workbook
        from django.utils import timezone as django_timezone
        path = '/api/order/shipments/export/'
        self.assertEqual(self.guest.get(path).status_code, 401)
        self.assertEqual(self.employee.get(path, {'month': '13'}).status_code, 400)
        item = self.request(self.employee, 'post', 'shipments/', {
            **self.payload, 'code': '0000123', 'buyerName': 'Nguyễn An', 'cnyPrice': '10.22',
            'weightFee': 10000, 'domesticFee': 2000, 'sharedFee': 5000, 'note': '=1+1',
        }).json()
        Shipment.objects.filter(pk=item['id']).update(created_at=datetime(2026, 9, 30, 18, tzinfo=timezone.utc))
        self.request(self.employee, 'post', f"shipments/{item['id']}/payments/", {
            'kind': 'receipt', 'amount': 10000, 'paidAt': django_timezone.now().isoformat(), 'note': 'Cọc lần 1',
        })
        self.request(self.employee, 'post', 'shipments/', {**self.payload, 'code': 'OTHER', 'buyerName': 'Bình'})
        response = self.employee.get(path, {'year': '2026', 'month': '10', 'q': 'NGUYỄN'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('.xlsx', response['Content-Disposition'])
        book = load_workbook(BytesIO(response.content))
        page = book['Don hang']
        self.assertEqual(page.max_row, 3)
        self.assertEqual(page['B2'].value, '0000123')
        self.assertEqual(page['B2'].data_type, 's')
        self.assertEqual(page['AA2'].value, '=1+1')
        self.assertEqual(page['AA2'].data_type, 's')
        self.assertEqual(page['N2'].value, 15000)
        self.assertEqual(page['U2'].value, 69000)
        self.assertEqual(page['V2'].value, 10000)
        self.assertEqual(page['W2'].value, 59000)
        self.assertEqual(page['AB2'].value, '2026-10-01 01:00:00')
        self.assertEqual(page['N3'].value, 15000)
        self.assertEqual(book['Thanh toan'].max_row, 2)
        self.assertGreater(book['Lich su'].max_row, 1)
        self.assertNotIn('Du lieu sao luu', book.sheetnames)
        empty = load_workbook(BytesIO(self.employee.get(path, {'q': 'no-match'}).content))
        self.assertEqual(empty['Don hang'].max_row, 2)
        self.assertEqual(empty['Don hang']['N2'].value, 0)

    def test_excel_backup_contains_all_raw_order_data_and_deleted_history(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from .models import ShipmentHistory, OrderContact
        item = self.request(self.employee, 'post', 'shipments/', {**self.payload, 'cnyPrice': '100'}).json()
        OrderContact.objects.create(url='https://example.com/order')
        ShipmentHistory.objects.create(code='DELETED', actor='Admin', action='delete', changes={'note': {'before': 'x' * 40000, 'after': None}})
        response = self.owner.get('/api/order/shipments/export/', {'backup': '1', 'q': 'no-match', 'month': '13'})
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(book['Don hang']['B2'].value, 'CN123')
        self.assertTrue(any(row[2] == 'DELETED' for row in book['Lich su'].iter_rows(min_row=2, values_only=True)))
        fragments = {}
        for model, pk, part, chunk in book['Du lieu sao luu'].iter_rows(min_row=2, values_only=True):
            fragments.setdefault((model, pk), {})[part] = chunk
        records = {key: json.loads(''.join(parts[i] for i in sorted(parts))) for key, parts in fragments.items()}
        stored = records[('shipment', item['id'])]
        self.assertEqual(stored['pricing_snapshot'], default_pricing())
        self.assertEqual(stored['cny_price'], '100.00')
        self.assertTrue(any(key[0] == 'contact' for key in records))
        self.assertTrue(any(key[0] == 'pricing_default' for key in records))
        self.assertTrue(any(key[0] == 'history' and value['changes'].get('note', {}).get('before') == 'x' * 40000 for key, value in records.items()))
        self.assertFalse(any(key[0] == 'account' for key in records))

    def setUp(self):
        cache.clear()
        self.admin = OrderAccount(username='boss', full_name='Admin', role='admin')
        self.admin.set_password('Strong-Password-48')
        self.admin.save()
        self.worker = OrderAccount(username='staff', full_name='Nhân viên', role='employee')
        self.worker.set_password('Worker-Password-48')
        self.worker.save()
        self.guest = Client()
        self.owner = self.client_for(self.admin)
        self.employee = self.client_for(self.worker)
        self.payload = {'code': 'CN123', 'trackingCode': 'YD123', 'name': 'Kiện hàng', 'note': '', 'status': 0}

    def client_for(self, account):
        client = Client()
        session = client.session
        session['order_account_id'] = account.pk
        session.save()
        return client

    def request(self, client, method, path, data=None):
        return getattr(client, method)('/api/order/' + path, data=json.dumps(data) if data is not None else '', content_type='application/json')

    def test_guest_can_lookup_and_quote_but_cannot_write_or_list(self):
        self.assertEqual(self.guest.get('/api/order/pricing/').status_code, 200)
        self.assertEqual(self.guest.get('/api/order/lookup/?code=missing').json(), {'items': []})
        for method, path, data in [('get', 'shipments/', None), ('post', 'shipments/', self.payload), ('put', 'pricing/', default_pricing()), ('get', 'employees/', None)]:
            self.assertEqual(self.request(self.guest, method, path, data).status_code, 401)

    def test_order_contact_is_public_but_only_admin_can_edit(self):
        payload = {'url': 'https://example.com/profile'}
        self.assertEqual(self.guest.get('/api/order/contact/').json(), {'url': ''})
        self.assertEqual(self.request(self.guest, 'put', 'contact/', payload).status_code, 401)
        self.assertEqual(self.request(self.employee, 'put', 'contact/', payload).status_code, 403)
        self.assertEqual(self.request(self.owner, 'put', 'contact/', payload).json(), payload)
        self.assertEqual(self.guest.get('/api/order/contact/').json(), payload)
        for url in ['javascript:alert(1)', 'ftp://example.com', 'not-a-url', 'https://' + 'a' * 500]:
            self.assertEqual(self.request(self.owner, 'put', 'contact/', {'url': url}).status_code, 400)
        self.assertEqual(self.request(self.owner, 'put', 'contact/', {'url': ''}).json(), {'url': ''})

    def test_order_creation_date_is_preserved_when_updating(self):
        created = self.request(self.owner, 'post', 'shipments/', self.payload).json()
        self.assertTrue(created['createdAt'])
        updated = self.request(self.owner, 'put', f"shipments/{created['id']}/", {
            **self.payload, 'status': 3, 'createdAt': '2000-01-01T00:00:00Z',
        }).json()
        self.assertEqual(updated['createdAt'], created['createdAt'])

    def test_payment_details_are_saved_listed_and_publicly_searchable(self):
        for client, payment_status in [(self.owner, 'deposit'), (self.employee, 'domestic_shipping')]:
            payload = {**self.payload, 'code': payment_status, 'paymentStatus': payment_status, 'remainingAmount': 125000}
            created = self.request(client, 'post', 'shipments/', payload)
            self.assertEqual(created.status_code, 201)
            pk = created.json()['id']
            listed = client.get('/api/order/shipments/').json()['items']
            self.assertEqual(next(s for s in listed if s['id'] == pk)['remainingAmount'], 125000)
            for code in [payment_status, 'YD123']:
                public = self.guest.get('/api/order/lookup/', {'code': code}).json()['items']
                item = next(s for s in public if s['id'] == pk)
                self.assertEqual(item['paymentStatus'], payment_status)
                self.assertEqual(item['remainingAmount'], 125000)
            # Older clients updating shipment progress must preserve payment details.
            preserved = self.request(client, 'put', f'shipments/{pk}/', {**self.payload, 'code': payment_status}).json()
            self.assertEqual(preserved['remainingAmount'], 125000)
            paid = self.request(client, 'put', f'shipments/{pk}/', {**payload, 'paymentStatus': 'paid'})
            self.assertEqual(paid.json()['remainingAmount'], 0)

    def test_invalid_payment_data_cannot_create_orders(self):
        for status in ['deposit', 'domestic_shipping']:
            for amount in [None, 0, -1, 1.5, True, '1000', 1000000000000]:
                response = self.request(self.employee, 'post', 'shipments/', {
                    **self.payload, 'paymentStatus': status, 'remainingAmount': amount,
                })
                self.assertEqual(response.status_code, 400)
        response = self.request(self.employee, 'post', 'shipments/', {**self.payload, 'paymentStatus': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Shipment.objects.count(), 0)
        created = self.request(self.employee, 'post', 'shipments/', self.payload).json()
        self.assertEqual(created['paymentStatus'], '')
        self.assertEqual(created['remainingAmount'], 0)

    def test_product_details_and_quick_updates(self):
        url = 'https://m.tb.cn/h.8B7e93e?tk=2D83TK0Rmbt'
        created = self.request(self.employee, 'post', 'shipments/', {
            **self.payload, 'cnyPrice': '125.50',
            'productUrl': f'【闲鱼】{url} HU293 「快来捡漏【商品】」\n点击链接直接打开',
        }).json()
        self.assertEqual(created['productUrl'], url)
        self.assertEqual(created['cnyPrice'], '125.50')
        path = f"shipments/{created['id']}/"
        updated = self.request(self.employee, 'patch', path, {'status': 3}).json()
        self.assertEqual(updated['status'], 3)
        self.assertEqual(updated['productUrl'], url)
        self.assertEqual(updated['name'], self.payload['name'])
        paid = self.request(self.employee, 'patch', path, {'paymentStatus': 'deposit', 'remainingAmount': 123000}).json()
        # Manual legacy fields cannot override the balance calculated from receipts.
        self.assertEqual(paid['remainingAmount'], 467000)
        self.assertEqual(paid['cnyPrice'], '125.50')
        self.assertEqual(self.request(self.employee, 'patch', path, {'paymentStatus': 'paid'}).json()['remainingAmount'], 467000)
        self.assertEqual(self.request(self.guest, 'patch', path, {'status': 2}).status_code, 401)
        self.assertEqual(self.request(self.employee, 'patch', path, {'code': 'OTHER'}).status_code, 400)

    def test_invalid_product_details(self):
        for price in ['NaN', 'Infinity', '-1', '1.001', '10000000000', True, 'wrong']:
            self.assertEqual(self.request(self.employee, 'post', 'shipments/', {**self.payload, 'cnyPrice': price}).status_code, 400)
        for url in ['javascript:alert(1)', 'not-a-url', 'https://']:
            self.assertEqual(self.request(self.employee, 'post', 'shipments/', {**self.payload, 'productUrl': url}).status_code, 400)

    def test_buyer_name_is_private_and_editable_by_both_roles(self):
        created = self.request(self.owner, 'post', 'shipments/', {
            **self.payload, 'buyerName': 'Nguyễn An',
        }).json()
        self.assertEqual(created['buyerName'], 'Nguyễn An')
        for client in [self.owner, self.employee]:
            self.assertEqual(client.get('/api/order/shipments/').json()['items'][0]['buyerName'], 'Nguyễn An')
        for client in [self.guest, self.owner, self.employee]:
            for code in ['CN123', 'YD123']:
                public = client.get('/api/order/lookup/', {'code': code}).json()['items'][0]
                self.assertNotIn('buyerName', public)
                self.assertNotIn('buyer_name', public)
        updated = self.request(self.employee, 'put', f"shipments/{created['id']}/", {
            **self.payload, 'buyerName': 'Trần Bình',
        })
        self.assertEqual(updated.json()['buyerName'], 'Trần Bình')
        invalid = self.request(self.employee, 'put', f"shipments/{created['id']}/", {
            **self.payload, 'buyerName': 'x' * 151,
        })
        self.assertEqual(invalid.status_code, 400)

    def test_both_roles_can_create_edit_delete_orders_and_tracking_codes(self):
        for index, client in enumerate([self.owner, self.employee]):
            response = self.request(client, 'post', 'shipments/', {**self.payload, 'code': f'cn{index}'})
            self.assertEqual(response.status_code, 201)
            pk = response.json()['id']
            updated = self.request(client, 'put', f'shipments/{pk}/', {**self.payload, 'code': f'NEW{index}', 'trackingCode': f'NEWYD{index}', 'status': 5})
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()['status'], 5)
            # A tracking code can also be removed independently of its order.
            self.assertEqual(self.request(client, 'put', f'shipments/{pk}/', {**self.payload, 'code': f'NEW{index}', 'trackingCode': ''}).json()['trackingCode'], '')
            self.assertEqual(self.request(client, 'delete', f'shipments/{pk}/').status_code, 200)
        self.assertEqual(Shipment.objects.count(), 0)

    def test_both_roles_can_edit_pricing_and_bad_tiers_are_rejected(self):
        for client in [self.owner, self.employee]:
            config = {'rate': 4000, 'tiers': [{'from': 0, 'value': 5, 'type': 'percent'}]}
            self.assertEqual(self.request(client, 'put', 'pricing/', config).status_code, 200)
            self.assertEqual(self.guest.get('/api/order/pricing/').json(), config)
            config['tiers'].append({'from': 0, 'value': 20, 'type': 'fixed'})
            self.assertEqual(self.request(client, 'put', 'pricing/', config).status_code, 400)

    def test_only_admin_can_create_delete_employees_and_role_cannot_be_forged(self):
        payload = {'username': 'newstaff', 'fullName': 'Nguyễn An', 'password': 'Complex-secret-49', 'role': 'admin'}
        self.assertEqual(self.request(self.employee, 'post', 'employees/', payload).status_code, 403)
        self.assertEqual(self.employee.get('/api/order/employees/').status_code, 403)
        self.assertEqual(self.request(self.employee, 'delete', f'employees/{self.admin.pk}/').status_code, 403)
        response = self.request(self.owner, 'post', 'employees/', payload)
        self.assertEqual(response.status_code, 201)
        account = OrderAccount.objects.get(pk=response.json()['id'])
        self.assertEqual(account.role, 'employee')
        self.assertNotIn('password', response.json())
        self.assertNotEqual(account.password, payload['password'])
        self.assertTrue(account.check_password(payload['password']))
        self.assertEqual(self.request(self.owner, 'delete', f'employees/{self.admin.pk}/').status_code, 404)
        self.assertEqual(self.request(self.owner, 'delete', f'employees/{account.pk}/').status_code, 200)

    def test_deleted_employee_session_is_immediately_rejected(self):
        self.assertEqual(self.request(self.owner, 'delete', f'employees/{self.worker.pk}/').status_code, 200)
        self.assertEqual(self.request(self.employee, 'post', 'shipments/', self.payload).status_code, 401)
        self.assertIsNone(self.employee.get('/api/order/session/').json()['user'])

    def test_login_logout_csrf_and_fake_legacy_token(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.request(client, 'post', 'login/', {'username': 'boss', 'password': 'Strong-Password-48'}).status_code, 403)
        csrf = client.get('/api/order/session/').json()['csrfToken']
        response = client.post('/api/order/login/', data=json.dumps({'username': 'BOSS', 'password': 'Strong-Password-48'}), content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['role'], 'admin')
        self.assertNotIn('password', response.json()['user'])
        csrf = response.json()['csrfToken']
        self.assertEqual(client.post('/api/order/logout/', HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(client.get('/api/order/shipments/').status_code, 401)
        self.assertEqual(self.guest.get('/api/order/shipments/', HTTP_AUTHORIZATION='Bearer mock-token-for-boss').status_code, 401)

    def test_duplicate_codes_and_public_lookup_by_order_or_tracking(self):
        self.assertEqual(self.request(self.employee, 'post', 'shipments/', self.payload).status_code, 201)
        self.assertEqual(self.request(self.employee, 'post', 'shipments/', {**self.payload, 'code': 'cn123'}).status_code, 409)
        for code in ['cn123', 'yd123']:
            items = self.guest.get('/api/order/lookup/', {'code': code}).json()['items']
            self.assertEqual(items[0]['code'], 'CN123')
            self.assertEqual(items[0]['trackingCode'], 'YD123')
        self.assertEqual(self.request(self.employee, 'post', 'shipments/', {**self.payload, 'code': 'other', 'status': 6}).status_code, 400)

    def test_login_failure_and_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.request(self.guest, 'post', 'login/', {'username': 'staff', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.request(self.guest, 'post', 'login/', {'username': 'staff', 'password': 'wrong'}).status_code, 429)

    def test_admin_command_hashes_password(self):
        with patch('order_app.management.commands.create_order_admin.getpass.getpass', return_value='Another-strong-secret-83'):
            call_command('create_order_admin', username='initialadmin', name='Initial Admin', verbosity=0)
        self.assertTrue(OrderAccount.objects.get(username='initialadmin').check_password('Another-strong-secret-83'))

    def test_shared_fee_and_net_received(self):
        payload = {**self.payload, 'cnyPrice': '125.50', 'sharedFee': 5000}
        created = self.request(self.employee, 'post', 'shipments/', payload)
        self.assertEqual(created.status_code, 201)
        item = created.json()
        self.assertEqual((item['laborFee'], item['sharedFee'], item['netReceived']), (15000, 5000, 10000))
        path = f"shipments/{item['id']}/"
        updated = self.request(self.employee, 'patch', path, {'status': 2}).json()
        self.assertEqual(updated['sharedFee'], 5000)
        updated = self.request(self.employee, 'patch', path, {'sharedFee': 8000}).json()
        self.assertEqual(updated['netReceived'], 7000)
        self.assertEqual(updated['cnyPrice'], '125.50')
        self.request(self.employee, 'patch', path, {'sharedFee': 5000})
        config = {'rate': 3600, 'tiers': [{'from': 0, 'type': 'percent', 'value': 2.5}]}
        OrderPricing.objects.update_or_create(pk=1, defaults={'config': config})
        listed = self.employee.get('/api/order/shipments/').json()['items'][0]
        self.assertEqual(listed['laborFee'], 15000)
        self.assertEqual(listed['netReceived'], 10000)
        public = self.guest.get('/api/order/lookup/?code=CN123').json()['items'][0]
        for key in ['laborFee', 'sharedFee', 'netReceived']:
            self.assertNotIn(key, public)
        for invalid in [-1, 1.5, True, '5000', 1000000000000]:
            response = self.request(self.employee, 'put', path, {**payload, 'sharedFee': invalid})
            self.assertEqual(response.status_code, 400)
        updated = self.request(self.employee, 'put', path, {**payload, 'cnyPrice': '', 'sharedFee': 0}).json()
        self.assertIsNone(updated['laborFee'])
        self.assertIsNone(updated['netReceived'])

    def test_frozen_pricing_reprice_and_history(self):
        config = {'rate': 3600, 'tiers': [{'from': 0, 'type': 'percent', 'value': 2.5}]}
        OrderPricing.objects.create(pk=1, config=config)
        payload = {**self.payload, 'cnyPrice': '100', 'sharedFee': 1000}
        item = self.request(self.employee, 'post', 'shipments/', payload).json()
        path = f"shipments/{item['id']}/"
        self.assertEqual((item['lockedRate'], item['laborFee']), (3600, 9000))
        config['rate'] = 4000
        self.request(self.owner, 'put', 'pricing/', config)
        # A client cannot overwrite snapshots or computed fees.
        updated = self.request(self.employee, 'put', path, {**payload, 'cnyPrice': '200', 'laborFee': 1, 'pricingSnapshot': config}).json()
        self.assertEqual((updated['lockedRate'], updated['laborFee']), (3600, 18000))
        repriced = self.request(self.owner, 'put', path, {**payload, 'reprice': True}).json()
        self.assertEqual((repriced['lockedRate'], repriced['laborFee']), (4000, 10000))
        history_path = path + 'history/'
        self.assertEqual(self.guest.get('/api/order/' + history_path).status_code, 401)
        entries = self.employee.get('/api/order/' + history_path).json()['items']
        self.assertEqual(len(entries), 3)
        self.assertIn('boss', entries[0]['actor'])
        self.assertEqual(entries[0]['changes']['lockedRate'], {'before': 3600, 'after': 4000})
        self.assertEqual(entries[-1]['action'], 'create')
        # No-op and invalid updates do not create audit entries.
        self.request(self.owner, 'patch', path, {'status': 0})
        self.request(self.owner, 'patch', path, {'sharedFee': -1})
        self.assertEqual(len(self.owner.get('/api/order/' + history_path).json()['items']), 3)
        from .models import ShipmentHistory
        self.request(self.owner, 'delete', path)
        self.assertEqual(ShipmentHistory.objects.filter(code='CN123', shipment__isnull=True).count(), 4)

    def test_payment_ledger_surcharge_and_refunds(self):
        from django.utils import timezone
        payload = {**self.payload, 'cnyPrice': '100', 'surcharge': 10000, 'surchargeNote': 'Ship'}
        item = self.request(self.employee, 'post', 'shipments/', payload).json()
        path = f"shipments/{item['id']}/"
        self.assertEqual(item['totalDue'], 385000)
        payment = {'kind': 'receipt', 'amount': 100000, 'paidAt': timezone.now().isoformat(), 'note': 'Cọc'}
        self.assertEqual(self.request(self.guest, 'post', path + 'payments/', payment).status_code, 401)
        response = self.request(self.employee, 'post', path + 'payments/', payment)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['shipment']['balance'], 285000)
        second = self.request(self.employee, 'post', path + 'payments/', {**payment, 'amount': 300000}).json()
        self.assertEqual(second['shipment']['balance'], -15000)
        self.assertEqual(second['shipment']['paymentStatus'], 'paid')
        refund = self.request(self.employee, 'post', path + 'payments/', {**payment, 'kind': 'refund', 'amount': 20000}).json()
        self.assertEqual(refund['shipment']['paidAmount'], 380000)
        self.assertEqual(refund['shipment']['remainingAmount'], 5000)
        self.assertEqual(len(refund['items']), 3)
        for invalid in [-1, True, 1.5, '1000', 1000000000000]:
            self.assertEqual(self.request(self.employee, 'post', path + 'payments/', {**payment, 'amount': invalid}).status_code, 400)
        self.assertEqual(self.request(self.employee, 'post', path + 'payments/', {**payment, 'kind': 'refund', 'amount': 400000}).status_code, 400)
        self.assertEqual(self.request(self.employee, 'delete', path).status_code, 400)
        self.assertEqual(self.request(self.employee, 'patch', path, {'paymentStatusOverride': 'paid'}).status_code, 200)
        updated = self.request(self.employee, 'put', path, {**payload, 'surcharge': 20000}).json()
        self.assertEqual(updated['balance'], 15000)
        self.assertEqual(updated['netReceived'], 15000)
        self.assertEqual(self.request(self.employee, 'put', path, {**payload, 'surcharge': -1}).status_code, 400)
        public = self.guest.get('/api/order/lookup/?code=CN123').json()['items'][0]
        self.assertEqual(public['remainingAmount'], 15000)
        self.assertNotIn('paidAmount', public)
        self.assertNotIn('surchargeNote', public)
        extra = self.request(self.employee, 'post', path + 'payments/', {**payment, 'kind': 'surcharge', 'amount': 25000}).json()['shipment']
        self.assertEqual(extra['surchargeTotal'], 45000)
        self.assertEqual(extra['paidAmount'], 380000)
        self.assertEqual(extra['balance'], 40000)
        self.assertEqual(extra['netReceived'], 15000)

    def test_surcharge_breakdown_and_ceil_amount_due(self):
        from django.utils import timezone
        OrderPricing.objects.create(pk=1, config={'rate': 3600.1, 'tiers': [{'from': 0, 'type': 'fixed', 'value': 15000}]})
        payload = {**self.payload, 'cnyPrice': '10.01', 'weightFee': 20000, 'domesticFee': 5000, 'surcharge': 1000}
        item = self.request(self.employee, 'post', 'shipments/', payload).json()
        path = f"shipments/{item['id']}/"
        # 10.01 * 3600.1 = 36037.001, always round up.
        self.assertEqual(item['baseAmount'], 36038)
        self.assertEqual(item['totalDue'], 78000)
        self.assertEqual(item['rawTotalDue'], 77038)
        self.assertEqual(item['remainingAmount'], 78000)
        self.assertEqual(item['weightFeeTotal'], 20000)
        self.assertEqual(item['domesticFeeTotal'], 5000)
        for category, amount in [('weight', 2000), ('domestic', 3000), ('other', 4000)]:
            response = self.request(self.employee, 'post', path + 'payments/', {
                'kind': 'surcharge', 'surchargeCategory': category, 'amount': amount, 'paidAt': timezone.now().isoformat(),
            })
            self.assertEqual(response.status_code, 201)
        item = response.json()['shipment']
        self.assertEqual((item['weightFeeTotal'], item['domesticFeeTotal'], item['otherFeeTotal']), (22000, 8000, 5000))
        self.assertEqual(item['surchargeTotal'], 35000)
        payment = {'kind': 'receipt', 'amount': 51038, 'paidAt': timezone.now().isoformat()}
        item = self.request(self.employee, 'post', path + 'payments/', payment).json()['shipment']
        self.assertEqual(item['remainingAmount'], 36000)
        self.assertEqual(item['paymentStatus'], 'domestic_shipping')
        item = self.request(self.employee, 'post', path + 'payments/', {**payment, 'amount': 35963}).json()['shipment']
        self.assertEqual((item['remainingAmount'], item['balance']), (0, -1))
        self.assertEqual(item['paymentStatus'], 'paid')
        self.assertEqual(self.request(self.employee, 'put', path, {**payload, 'weightFee': -1}).status_code, 400)

    def test_manual_payment_status_and_round_up_to_thousand(self):
        from django.utils import timezone
        item = self.request(self.employee, 'post', 'shipments/', {**self.payload, 'cnyPrice': '10.22'}).json()
        path = f"shipments/{item['id']}/"
        self.assertEqual(item['totalDue'], 57000)
        self.assertEqual(item['roundingAdjustment'], 208)
        payload = {'kind': 'receipt', 'amount': 210, 'paidAt': timezone.now().isoformat()}
        item = self.request(self.employee, 'post', path + 'payments/', payload).json()['shipment']
        self.assertEqual(item['balance'], 56790)
        self.assertEqual(item['remainingAmount'], 57000)
        changed = self.request(self.employee, 'patch', path, {'paymentStatusOverride': 'paid'}).json()
        self.assertEqual(changed['paymentStatus'], 'paid')
        self.assertEqual(changed['paidAmount'], 210)
        self.assertEqual(changed['remainingAmount'], 57000)
        changed = self.request(self.employee, 'put', path, {**changed, 'paymentStatusOverride': 'domestic_shipping'}).json()
        self.assertEqual(changed['paymentStatus'], 'domestic_shipping')
        changed = self.request(self.employee, 'patch', path, {'status': 2}).json()
        self.assertEqual(changed['paymentStatus'], 'domestic_shipping')
        public = self.guest.get('/api/order/lookup/?code=CN123').json()['items'][0]
        self.assertEqual(public['paymentStatus'], 'domestic_shipping')
        automatic = self.request(self.employee, 'patch', path, {'paymentStatusOverride': None}).json()
        self.assertEqual(automatic['paymentStatus'], 'deposit')
        self.assertEqual(self.request(self.employee, 'patch', path, {'paymentStatusOverride': 'invalid'}).status_code, 400)
