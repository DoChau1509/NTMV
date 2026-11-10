import json
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from functools import wraps
from django.core.cache import cache
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token, rotate_token
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import ShipmentPayment
from .models import OrderAccount, OrderPricing, OrderContact, Shipment, ShipmentHistory, default_pricing
from .pricing import calculate_fee
from .excel import workbook, VN

# Vẫn kiểm tra hash khi tài khoản không tồn tại để hạn chế lộ tên qua thời gian xử lý.
DUMMY_PASSWORD = make_password('unused-login-timing-value')


# Trả thông tin tài khoản cho giao diện, không gửi hash mật khẩu.
def serialize_account(account):
    return {'id': str(account.pk), 'username': account.username, 'fullName': account.full_name, 'role': account.role}


# Các trường người mua, giá nhập và link sản phẩm chỉ có trong phản hồi nội bộ.
def serialize_shipment(item, private=False, config=None):
    payments = list(item.payments.all())
    received = sum(p.amount if p.kind == 'receipt' else -p.amount if p.kind == 'refund' else 0 for p in payments)
    weight_fee = item.weight_fee + sum(p.amount for p in payments if p.kind == 'surcharge' and p.surcharge_category == 'weight')
    domestic_fee = item.domestic_fee + sum(p.amount for p in payments if p.kind == 'surcharge' and p.surcharge_category == 'domestic')
    other_fee = item.surcharge + sum(p.amount for p in payments if p.kind == 'surcharge' and p.surcharge_category == 'other')
    surcharge_total = weight_fee + domestic_fee + other_fee
    total = None
    base = None
    if item.cny_price is not None and item.labor_fee is not None and item.pricing_snapshot.get('rate'):
        base = int((item.cny_price * Decimal(str(item.pricing_snapshot['rate']))).quantize(Decimal('1'), rounding=ROUND_CEILING))
        total = base + item.labor_fee + surcharge_total
    raw_total = total
    if total is not None:
        total = ((total + 999) // 1000) * 1000
    data = {'id': str(item.pk), 'code': item.code, 'trackingCode': item.tracking_code,
            'name': item.name, 'status': item.status, 'note': item.note,
            'paymentStatus': item.payment_status, 'remainingAmount': item.remaining_amount,
            'createdAt': item.created_at.isoformat(), 'updatedAt': item.updated_at.isoformat()}
    if total is not None:
        data['remainingAmount'] = ((max(0, total - received) + 999) // 1000) * 1000
        if received >= total:
            data['paymentStatus'] = 'paid'
        elif received >= base + item.labor_fee:
            data['paymentStatus'] = 'domestic_shipping'
        else:
            data['paymentStatus'] = 'deposit' if received > 0 else ''
    if item.payment_status_override is not None:
        data['paymentStatus'] = item.payment_status_override
    if private:
        data['buyerName'] = item.buyer_name
        data['cnyPrice'] = str(item.cny_price) if item.cny_price is not None else None
        data['productUrl'] = item.product_url
        config = item.pricing_snapshot
        fee = item.labor_fee
        data['pricingSnapshot'] = config
        data['lockedRate'] = config.get('rate')
        data['laborFee'] = fee
        data['sharedFee'] = item.shared_fee
        data['netReceived'] = fee - item.shared_fee if fee is not None else None
        data.update(surchargeTotal=surcharge_total, surcharge=item.surcharge, surchargeNote=item.surcharge_note, totalDue=total,
                    paymentStatusOverride=item.payment_status_override,
                    rawTotalDue=raw_total, roundingAdjustment=total - raw_total if total is not None else None,
                    paidAmount=received, balance=total - received if total is not None else None,
                    paymentCount=len(payments), baseAmount=base,
                    weightFee=item.weight_fee, domesticFee=item.domestic_fee,
                    weightFeeTotal=weight_fee, domesticFeeTotal=domestic_fee, otherFeeTotal=other_fee)
    return data


# Dùng chung kiểm tra phương thức, phiên đăng nhập, quyền và lỗi dữ liệu cho API.
def endpoint(methods, access='public'):
    def decorate(view):
        @never_cache
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({'error': 'Phương thức không hợp lệ.'}, status=405)
            request.order_account = OrderAccount.objects.filter(pk=request.session.get('order_account_id')).first()
            if access != 'public' and request.order_account is None:
                return JsonResponse({'error': 'Vui lòng đăng nhập.'}, status=401)
            if access == 'employee' and request.order_account.role not in ('admin', 'employee'):
                return JsonResponse({'error': 'Chỉ admin và nhân viên được thao tác.'}, status=403)
            if access == 'admin' and request.order_account.role != 'admin':
                return JsonResponse({'error': 'Chỉ admin được quản lý tài khoản nhân viên.'}, status=403)
            try:
                return view(request, *args, **kwargs)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                return JsonResponse({'error': 'Dữ liệu không hợp lệ.'}, status=400)
            except IntegrityError:
                return JsonResponse({'error': 'Mã đơn hoặc tài khoản đã tồn tại.'}, status=409)
        return wrapped
    return decorate


# Chỉ nhận JSON dạng đối tượng để các API đọc trường dữ liệu nhất quán.
def body(request):
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError()
    return data


# Kiểm tra chuỗi và giới hạn độ dài; giữ nguyên khoảng trắng của mật khẩu.
def text(data, key, limit, required=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError()
    return value if key == 'password' else value.strip()


@endpoint(['GET'])
def session_view(request):
    # Khôi phục tài khoản theo cookie phiên và cấp token CSRF cho frontend.
    return JsonResponse({'user': serialize_account(request.order_account) if request.order_account else None, 'csrfToken': get_token(request)})


@endpoint(['POST'])
def login_view(request):
    data = body(request)
    username = text(data, 'username', 100, True).lower()
    password = text(data, 'password', 128, True)
    # Giới hạn đăng nhập sai theo IP và tên tài khoản, không tiết lộ tài khoản tồn tại.
    key = 'order-login:' + request.META.get('REMOTE_ADDR', '') + ':' + username
    attempts = cache.get(key, 0)
    if attempts >= 10:
        return JsonResponse({'error': 'Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau 5 phút.'}, status=429)
    account = OrderAccount.objects.filter(username=username).first()
    valid = account.check_password(password) if account else check_password(password, DUMMY_PASSWORD)
    if not account or not valid:
        cache.set(key, attempts + 1, 300)
        return JsonResponse({'error': 'Tên đăng nhập hoặc mật khẩu không đúng.'}, status=401)
    cache.delete(key)
    # Tạo phiên mới có hạn 8 giờ và đổi token CSRF sau khi đăng nhập thành công.
    request.session.flush()
    request.session['order_account_id'] = account.pk
    request.session.set_expiry(8 * 60 * 60)
    rotate_token(request)
    return JsonResponse({'user': serialize_account(account), 'csrfToken': get_token(request)})


@endpoint(['POST'])
def logout_view(request):
    # Xóa phiên hiện tại và cấp lại token để trình duyệt có thể đăng nhập tiếp.
    request.session.flush()
    rotate_token(request)
    return JsonResponse({'csrfToken': get_token(request)})


# Kiểm tra tỷ giá và thang công ở máy chủ, kể cả khi frontend đã kiểm tra.
def valid_config(config):
    def number(value, low, high):
        return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
    if not isinstance(config, dict) or not number(config.get('rate'), 0.000001, 1e6):
        return False
    tiers = config.get('tiers')
    if not isinstance(tiers, list) or not 1 <= len(tiers) <= 100:
        return False
    previous = -1
    for i, tier in enumerate(tiers):
        if not isinstance(tier, dict):
            return False
        start = tier.get('from')
        if not number(start, 0, 1e9) or (i == 0 and start != 0) or start <= previous:
            return False
        if tier.get('type') not in ('fixed', 'percent') or not number(tier.get('value'), 0, 100 if tier['type'] == 'percent' else 1e9):
            return False
        previous = start
    return True


@endpoint(['GET', 'PUT'])
def contact_view(request):
    # Khách được đọc liên kết; chỉ admin được sửa bản cấu hình chung có khóa 1.
    if request.method == 'PUT':
        if not request.order_account:
            return JsonResponse({'error': 'Vui lòng đăng nhập.'}, status=401)
        if request.order_account.role != 'admin':
            return JsonResponse({'error': 'Chỉ admin được sửa liên kết đặt hàng.'}, status=403)
        url = text(body(request), 'url', 500)
        if url:
            try:
                URLValidator(schemes=['http', 'https'])(url)
            except ValidationError:
                return JsonResponse({'error': 'Vui lòng nhập đường link http:// hoặc https:// hợp lệ.'}, status=400)
        OrderContact.objects.update_or_create(pk=1, defaults={'url': url})
        return JsonResponse({'url': url})
    contact = OrderContact.objects.filter(pk=1).first()
    return JsonResponse({'url': contact.url if contact else ''})


@endpoint(['GET', 'PUT'])
def pricing_view(request):
    # Đọc cấu hình chung; tài khoản đã đăng nhập được lưu cấu hình hợp lệ.
    if request.method == 'PUT':
        if not request.order_account:
            return JsonResponse({'error': 'Vui lòng đăng nhập.'}, status=401)
        config = body(request)
        if not valid_config(config):
            return JsonResponse({'error': 'Tỷ giá hoặc thang công không hợp lệ. Các bậc phải tăng dần từ 0.'}, status=400)
        OrderPricing.objects.update_or_create(pk=1, defaults={'config': config})
        return JsonResponse(config)
    pricing = OrderPricing.objects.filter(pk=1).first()
    return JsonResponse(pricing.config if pricing else default_pricing())


@endpoint(['GET'])
def lookup_view(request):
    code = request.GET.get('code', '').strip().upper()
    if not code or len(code) > 100:
        return JsonResponse({'error': 'Vui lòng nhập mã đơn hoặc mã vận đơn hợp lệ.'}, status=400)
    # Khách chỉ tra bằng mã chính xác, không được liệt kê toàn bộ đơn hàng.
    items = Shipment.objects.filter(code=code) | Shipment.objects.filter(tracking_code=code)
    return JsonResponse({'items': [serialize_shipment(s) for s in items.order_by('-updated_at')]})


@endpoint(['GET', 'POST'], 'employee')
def shipments_view(request):
    # Nhân viên/admin được xem dữ liệu nội bộ và thêm đơn hàng.
    if request.method == 'GET':
        return JsonResponse({'items': [serialize_shipment(s, private=True) for s in Shipment.objects.prefetch_related('payments').order_by('-updated_at')]})
    return save_shipment(request)


def save_shipment(request, item=None):
    data = body(request)
    before = serialize_shipment(item, private=True) if item else {}
    if item and item.payments.exists():
        if request.method == 'PATCH' and 'remainingAmount' in data:
            return JsonResponse({'error': 'Đơn đã có sổ thanh toán. Vui lòng ghi khoản thu hoặc hoàn tiền trong sổ.'}, status=400)
    status_override = data.get('paymentStatusOverride', item.payment_status_override if item else None)
    if request.method == 'PATCH' and 'paymentStatus' in data and 'paymentStatusOverride' not in data:
        status_override = data['paymentStatus']
    if status_override is not None and status_override not in ('', 'paid', 'deposit', 'domestic_shipping'):
        return JsonResponse({'error': 'Trạng thái thanh toán không hợp lệ.'}, status=400)
    # Cập nhật nhanh chỉ nhận trạng thái và thanh toán; giữ các trường cũ còn lại.
    if request.method == 'PATCH':
        allowed = {'status', 'paymentStatus', 'paymentStatusOverride', 'remainingAmount', 'sharedFee'}
        if not data or not set(data).issubset(allowed):
            raise ValueError()
        data = {**serialize_shipment(item, private=True), **data}
    code = text(data, 'code', 100, True).upper()
    tracking_code = text(data, 'trackingCode', 100).upper()
    name = text(data, 'name', 200, True)
    buyer_name = text(data, 'buyerName', 150) if 'buyerName' in data else (item.buyer_name if item else '')
    note = text(data, 'note', 1000)
    raw_price = data.get('cnyPrice', item.cny_price if item else None)
    shared_fee = data.get('sharedFee', item.shared_fee if item else 0)
    surcharge = data.get('surcharge', item.surcharge if item else 0)
    weight_fee = data.get('weightFee', item.weight_fee if item else 0)
    domestic_fee = data.get('domesticFee', item.domestic_fee if item else 0)
    if any(type(value) is not int or not 0 <= value <= 999999999999 for value in (weight_fee, domestic_fee)):
        return JsonResponse({'error': 'Phí cân và phí nội địa phải là số nguyên VNĐ từ 0 đến 999.999.999.999.'}, status=400)
    surcharge_note = text(data, 'surchargeNote', 500) if 'surchargeNote' in data else (item.surcharge_note if item else '')
    if type(surcharge) is not int or not 0 <= surcharge <= 999999999999:
        return JsonResponse({'error': 'Phụ phí phải là số nguyên VNĐ từ 0 đến 999.999.999.999.'}, status=400)
    if type(shared_fee) is not int or not 0 <= shared_fee <= 999999999999:
        return JsonResponse({'error': 'Công chia phải là số nguyên VNĐ từ 0 đến 999.999.999.999.'}, status=400)
    # Dùng Decimal để kiểm tra giá tệ với tối đa hai chữ số thập phân.
    try:
        cny_price = None if raw_price is None or raw_price == '' else Decimal(str(raw_price))
        if cny_price is not None and (not cny_price.is_finite() or not 0 <= cny_price <= Decimal('9999999999.99') or cny_price != cny_price.quantize(Decimal('.01'))):
            raise InvalidOperation()
    except InvalidOperation:
        return JsonResponse({'error': 'Giá tệ phải từ 0 đến 9.999.999.999,99 và tối đa 2 chữ số thập phân.'}, status=400)
    if item and item.payments.exists() and (cny_price is None or cny_price <= 0):
        return JsonResponse({'error': 'Đơn có giao dịch thanh toán phải giữ giá tệ lớn hơn 0.'}, status=400)
    product_url = text(data, 'productUrl', 10000) if 'productUrl' in data else (item.product_url if item else '')
    if product_url:
        # Tách URL khỏi đoạn chia sẻ sản phẩm rồi kiểm tra giao thức và độ dài.
        match = re.search(r'https?://[^\s<>"\u3010\u3011\u300c\u300d]+', product_url)
        product_url = match.group(0).rstrip('.,;!，。；！') if match else product_url
        try:
            URLValidator(schemes=['http', 'https'])(product_url)
            if len(product_url) > 2000:
                raise ValidationError('URL too long')
        except ValidationError:
            return JsonResponse({'error': 'Vui lòng nhập đường link sản phẩm http:// hoặc https:// hợp lệ.'}, status=400)
    status = data.get('status')
    if type(status) is not int or not 0 <= status <= 5:
        raise ValueError()
    payment_status = data.get('paymentStatus', item.payment_status if item else '')
    remaining_amount = data.get('remainingAmount', item.remaining_amount if item else 0)
    if item and item.payments.exists():
        payment_status, remaining_amount = item.payment_status, item.remaining_amount
    if payment_status not in ('', 'paid', 'deposit', 'domestic_shipping'):
        return JsonResponse({'error': 'Trạng thái thanh toán không hợp lệ.'}, status=400)
    if payment_status in ('deposit', 'domestic_shipping'):
        # Hai trạng thái còn nợ bắt buộc có số tiền nguyên VNĐ lớn hơn 0.
        if type(remaining_amount) is not int or not 0 < remaining_amount <= 999999999999:
            return JsonResponse({'error': 'Số tiền còn lại phải là số nguyên VNĐ lớn hơn 0, tối đa 999.999.999.999.'}, status=400)
    else:
        remaining_amount = 0
    # Lưu toàn bộ thông tin đơn trong cùng một giao dịch cơ sở dữ liệu.
    with transaction.atomic():
        item = item or Shipment()
        reprice = data.get('reprice', False)
        if type(reprice) is not bool:
            raise ValueError()
        if not item.pricing_snapshot or reprice:
            pricing = OrderPricing.objects.filter(pk=1).first()
            item.pricing_snapshot = pricing.config if pricing else default_pricing()
        item.labor_fee = calculate_fee(cny_price, item.pricing_snapshot)
        item.code, item.tracking_code, item.name, item.note, item.status = code, tracking_code, name, note, status
        item.buyer_name = buyer_name
        item.payment_status = payment_status
        item.payment_status_override = status_override
        item.remaining_amount = remaining_amount
        item.cny_price = cny_price
        item.shared_fee = shared_fee
        item.surcharge = surcharge
        item.weight_fee = weight_fee
        item.domestic_fee = domestic_fee
        item.surcharge_note = surcharge_note
        item.product_url = product_url
        item.save()
        after = serialize_shipment(item, private=True)
        changes = {key: {'before': before.get(key), 'after': value}
                   for key, value in after.items()
                   if key not in ('id', 'createdAt', 'updatedAt', 'netReceived') and before.get(key) != value}
        if changes:
            ShipmentHistory.objects.create(shipment=item, code=item.code,
                actor=f'{request.order_account.full_name} ({request.order_account.username})',
                action='update' if before else 'create', changes=changes)
    return JsonResponse(serialize_shipment(item, private=True), status=200 if request.method in ('PUT', 'PATCH') else 201)


@endpoint(['PUT', 'PATCH', 'DELETE'], 'employee')
@transaction.atomic
def shipment_detail(request, pk):
    # Tìm đơn theo khóa chính trước khi xóa hoặc chuyển sang xử lý cập nhật.
    item = Shipment.objects.select_for_update().filter(pk=pk).first()
    if not item:
        return JsonResponse({'error': 'Không tìm thấy đơn hàng.'}, status=404)
    if request.method == 'DELETE':
        if item.payments.exists():
            return JsonResponse({'error': 'Không thể xóa đơn đã có giao dịch thanh toán.'}, status=400)
        with transaction.atomic():
            ShipmentHistory.objects.create(shipment=item, code=item.code,
                actor=f'{request.order_account.full_name} ({request.order_account.username})',
                action='delete', changes={'code': {'before': item.code, 'after': None}})
            item.delete()
        return JsonResponse({'ok': True})
    return save_shipment(request, item)


@endpoint(['GET', 'POST'], 'admin')
def employees_view(request):
    if request.method == 'GET':
        return JsonResponse({'items': [serialize_account(a) for a in OrderAccount.objects.filter(role='employee').order_by('username')]})
    data = body(request)
    username = text(data, 'username', 100, True).lower()
    if not re.fullmatch(r'[a-z0-9_.@+-]+', username):
        return JsonResponse({'error': 'Tên đăng nhập chỉ dùng chữ không dấu, số và các ký tự _.@+-.'}, status=400)
    name = text(data, 'fullName', 150, True)
    password = text(data, 'password', 128, True)
    try:
        validate_password(password)
    except ValidationError:
        return JsonResponse({'error': 'Mật khẩu cần ít nhất 8 ký tự, không quá phổ biến và không chỉ chứa số.'}, status=400)
    # Luôn tạo vai trò nhân viên, không nhận vai trò do frontend gửi lên.
    account = OrderAccount(username=username, full_name=name, role='employee')
    account.set_password(password)
    with transaction.atomic():
        account.save()
    return JsonResponse(serialize_account(account), status=201)


@endpoint(['DELETE'], 'admin')
def employee_detail(request, pk):
    # Chỉ xóa tài khoản nhân viên; tài khoản admin không khớp truy vấn này.
    account = OrderAccount.objects.filter(pk=pk, role='employee').first()
    if not account:
        return JsonResponse({'error': 'Không tìm thấy tài khoản nhân viên.'}, status=404)
    account.delete()
    return JsonResponse({'ok': True})


@endpoint(['GET'], 'employee')
def shipment_history(request, pk):
    return JsonResponse({'items': [
        {'id': str(row.pk), 'code': row.code, 'actor': row.actor, 'action': row.action,
         'changes': row.changes, 'createdAt': row.created_at.isoformat()}
        for row in ShipmentHistory.objects.filter(shipment_id=pk).order_by('-created_at', '-pk')
    ]})


@endpoint(['GET'], 'employee')
@transaction.atomic
def shipment_export(request):
    backup = request.GET.get('backup') == '1'
    year, month = request.GET.get('year', ''), request.GET.get('month', '')
    query = request.GET.get('q', '').strip().lower()
    if not backup and ((year and (not year.isdigit() or not 1 <= int(year) <= 9999)) or
                       (month and (not month.isdigit() or not 1 <= int(month) <= 12))):
        return JsonResponse({'error': 'Bộ lọc tháng/năm không hợp lệ.'}, status=400)
    items = list(Shipment.objects.prefetch_related('payments').order_by('-updated_at'))
    if not backup:
        items = [item for item in items
                 if (not year or (item.created_at or item.updated_at).astimezone(VN).year == int(year))
                 and (not month or (item.created_at or item.updated_at).astimezone(VN).month == int(month))
                 and query in f'{item.buyer_name} {item.code} {item.tracking_code} {item.name}'.lower()]
    ids = [item.pk for item in items]
    payments = list(ShipmentPayment.objects.filter(shipment_id__in=ids).select_related('shipment').order_by('-paid_at', '-pk'))
    history = list((ShipmentHistory.objects.all() if backup else ShipmentHistory.objects.filter(shipment_id__in=ids)).order_by('-created_at', '-pk'))
    now = timezone.now().astimezone(VN)
    metadata = [
        ['Loại file', 'Sao lưu toàn bộ đơn hàng' if backup else 'Xuất đơn theo bộ lọc'],
        ['Thời điểm xuất (giờ Việt Nam)', now.strftime('%Y-%m-%d %H:%M:%S')],
        ['Người xuất', f'{request.order_account.full_name} ({request.order_account.username})'],
        ['Phạm vi', 'Tất cả đơn, thanh toán, lịch sử (kể cả lịch sử đơn đã xóa)' if backup else f'Năm: {year or "Tất cả"}; tháng: {month or "Tất cả"}; từ khóa: {query or "Không"}'],
        ['Số đơn', len(items)],
        ['Đơn vị', 'VNĐ; giá tệ là CNY. Tổng tiền và số cần trả làm tròn lên 1.000đ.'],
        ['Tổng thực nhận', 'Chỉ cộng các đơn đã xác định tiền công; thực nhận = tiền công trừ công chia.'],
    ]
    raw = []
    if backup:
        metadata.extend([
            ['Phiên bản sao lưu', 'order-excel-v1'],
            ['Dữ liệu sao lưu', 'Giữ nguyên các phần dữ liệu JSON theo loại, ID và thứ tự phần; gồm giá đã chốt, khoản thu/hoàn/phụ phí, lịch sử, bảng giá và liên hệ.'],
            ['Phạm vi sao lưu', 'Dữ liệu đơn hàng; không chứa tài khoản hoặc mật khẩu. Chưa có chức năng nhập khôi phục tự động.'],
        ])
        for model, records in [('shipment', items), ('payment', payments), ('history', history),
                               ('pricing', OrderPricing.objects.all()), ('contact', OrderContact.objects.all())]:
            for record in records:
                raw.append((model, record.pk, {field.attname: getattr(record, field.attname) for field in record._meta.fields}))
        if not OrderPricing.objects.exists():
            raw.append(('pricing_default', 'default', default_pricing()))
    content = workbook([serialize_shipment(item, private=True) for item in items], payments, history, metadata, raw)
    response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f'{"sao-luu-don-hang" if backup else "don-hang"}-{now:%Y%m%d-%H%M%S}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@endpoint(['GET', 'POST'], 'employee')
@transaction.atomic
def shipment_payments(request, pk):
    item = Shipment.objects.select_for_update().filter(pk=pk).first()
    if not item:
        return JsonResponse({'error': 'Không tìm thấy đơn hàng.'}, status=404)
    if request.method == 'POST':
        data = body(request)
        amount = data.get('amount')
        kind = data.get('kind')
        category = data.get('surchargeCategory', 'other') if kind == 'surcharge' else 'other'
        if category not in ('weight', 'domestic', 'other'):
            return JsonResponse({'error': 'Loại phụ phí không hợp lệ.'}, status=400)
        if type(amount) is not int or not 0 < amount <= 999999999999 or kind not in ('receipt', 'refund', 'surcharge'):
            return JsonResponse({'error': 'Số tiền phải là số nguyên VNĐ lớn hơn 0, tối đa 999.999.999.999. Loại giao dịch phải là thu hoặc hoàn tiền.'}, status=400)
        paid_at = parse_datetime(text(data, 'paidAt', 40, True))
        if paid_at is None or timezone.is_naive(paid_at) or paid_at > timezone.now():
            return JsonResponse({'error': 'Thời điểm thanh toán không hợp lệ hoặc nằm trong tương lai.'}, status=400)
        before = serialize_shipment(item, private=True)
        if before['totalDue'] is None:
            return JsonResponse({'error': 'Vui lòng nhập giá tệ trước khi ghi thanh toán.'}, status=400)
        if kind == 'refund' and amount > before['paidAmount']:
            return JsonResponse({'error': 'Số tiền hoàn vượt quá số tiền đã thu sau hoàn tiền.'}, status=400)
        actor = f'{request.order_account.full_name} ({request.order_account.username})'
        payment = ShipmentPayment.objects.create(shipment=item, kind=kind, amount=amount, surcharge_category=category,
            paid_at=paid_at, note=text(data, 'note', 500), actor=actor)
        item.save(update_fields=['updated_at'])
        after = serialize_shipment(item, private=True)
        ShipmentHistory.objects.create(shipment=item, code=item.code, actor=actor, action='update', changes={
            {'receipt': 'paymentReceipt', 'refund': 'paymentRefund', 'surcharge': 'paymentSurcharge'}[kind]: {'before': None, 'after': amount},
            'paidAmount': {'before': before['paidAmount'], 'after': after['paidAmount']},
            'balance': {'before': before['balance'], 'after': after['balance']},
            **({'surchargeCategory': {'before': None, 'after': category}} if kind == 'surcharge' else {}),
        })
    return JsonResponse({'shipment': serialize_shipment(item, private=True), 'items': [
        {'id': str(p.pk), 'kind': p.kind, 'surchargeCategory': p.surcharge_category, 'amount': p.amount, 'paidAt': p.paid_at.isoformat(),
         'note': p.note, 'actor': p.actor, 'createdAt': p.created_at.isoformat()}
        for p in item.payments.order_by('-paid_at', '-pk')
    ]}, status=201 if request.method == 'POST' else 200)
