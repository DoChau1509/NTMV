"""Internal gathering folders, customer orders and product lines."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import Gathering, GatheringOrder, GatheringItem
from .views import body, endpoint


def invalid(message):
    raise ValueError(message)


def string(data, key, limit, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        invalid(key)
    return value.strip()


def day(value):
    if not isinstance(value, str):
        invalid('date')
    return date.fromisoformat(value)


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        invalid('integer')
    return value


def price(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        invalid('price')
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not 0 <= result <= Decimal('9999999999.99') or result != result.quantize(Decimal('.01')):
            invalid('price')
    except InvalidOperation:
        invalid('price')
    return result


def item_data(data):
    if not isinstance(data, dict):
        invalid('item')
    status = data.get('status')
    if status not in ('not_bought', 'bought', 'arrived', 'shipped'):
        invalid('status')
    due_value = data.get('depositDueOn')
    due = day(due_value) if due_value is not None and due_value != '' else None
    fields = dict(name=string(data, 'name', 200), quantity=integer(data.get('quantity'), 1, 1000000),
                  unit_price=price(data.get('unitPrice')), deposit_due_on=due, status=status)
    if 'unitPriceVnd' in data:
        value = data['unitPriceVnd']
        fields['unit_price_vnd'] = integer(value, 0, 1000000000000) if value is not None else None
    if 'note' in data:
        fields['note'] = string(data, 'note', 2000, required=False)
    return fields


def order_json(order):
    today = timezone.localdate()
    rows = []
    total = Decimal('0.00')
    items = list(order.items.all())
    subtotal_vnd = sum(item.unit_price_vnd * item.quantity for item in items) if all(item.unit_price_vnd is not None for item in items) else None
    total_vnd = subtotal_vnd - order.discount_amount if subtotal_vnd is not None else None
    remaining = max(0, total_vnd - order.paid_amount) if total_vnd is not None else None
    for item in items:
        subtotal = item.unit_price * item.quantity
        total += subtotal
        days = (item.deposit_due_on - today).days if remaining != 0 and item.deposit_due_on else None
        rows.append(dict(id=str(item.pk), name=item.name, note=item.note, quantity=item.quantity, unitPrice=f'{item.unit_price:.2f}',
                         totalCny=f'{subtotal:.2f}', unitPriceVnd=item.unit_price_vnd,
                         depositDueOn=item.deposit_due_on.isoformat() if item.deposit_due_on else None,
                         status=item.status, deadlineAlert=('overdue' if days < 0 else 'due_soon') if days is not None and days <= 1 else None))
    return dict(id=str(order.pk), gatheringId=str(order.gathering_id), customerName=order.customer_name,
                profileUrl=order.profile_url, paidAmount=order.paid_amount, remainingAmount=str(remaining) if remaining is not None else None,
                totalCny=f'{total:.2f}', discountAmount=order.discount_amount,
                subtotalVnd=str(subtotal_vnd) if subtotal_vnd is not None else None,
                totalVnd=str(total_vnd) if total_vnd is not None else None, items=rows,
                updatedAt=order.updated_at.isoformat())


def gathering_json(gathering):
    orders = [order_json(order) for order in gathering.orders.all()]
    return dict(id=str(gathering.pk), name=gathering.name, startsOn=gathering.starts_on.isoformat(),
                endsOn=gathering.ends_on.isoformat(), orders=orders)


def gathering_fields(data):
    start, end = day(data.get('startsOn')), day(data.get('endsOn'))
    if end < start:
        invalid('date range')
    return dict(name=string(data, 'name', 200), starts_on=start, ends_on=end)


@endpoint(['GET', 'POST'], access='employee')
def gatherings(request):
    if request.method == 'GET':
        records = Gathering.objects.prefetch_related('orders__items').order_by('-starts_on', '-pk')
        return JsonResponse({'items': [gathering_json(row) for row in records]})
    gathering = Gathering.objects.create(**gathering_fields(body(request)))
    return JsonResponse(gathering_json(gathering), status=201)


@endpoint(['PUT', 'DELETE'], access='employee')
def gathering_detail(request, pk):
    with transaction.atomic():
        gathering = Gathering.objects.select_for_update().filter(pk=pk).first()
        if gathering is None:
            return JsonResponse({'error': 'Không tìm thấy đợt gom.'}, status=404)
        if request.method == 'DELETE':
            if gathering.orders.exists():
                return JsonResponse({'error': 'Đợt gom còn đơn khách. Hãy xóa từng đơn trước khi xóa đợt gom.'}, status=409)
            gathering.delete()
            return JsonResponse({'ok': True})
        for field, value in gathering_fields(body(request)).items():
            setattr(gathering, field, value)
        gathering.save()
        return JsonResponse(gathering_json(gathering))


def save_order(request, gathering, order=None):
    data = body(request)
    name = string(data, 'customerName', 150)
    url = string(data, 'profileUrl', 500, required=False)
    if url:
        try:
            URLValidator(schemes=['http', 'https'])(url)
        except ValidationError:
            invalid('profile URL')
    paid = integer(data.get('paidAmount'), 0, 1000000000000)
    discount = integer(data.get('discountAmount', order.discount_amount if order else 0), 0, 1000000000000)
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        invalid('items')
    values = [item_data(item) for item in items]
    existing = {str(item.pk): item for item in order.items.all()} if order else {}
    used = set()
    for row in items:
        pk = row.get('id')
        if pk is not None:
            if not isinstance(pk, str) or pk not in existing or pk in used:
                invalid('item ownership')
            used.add(pk)
    prices_vnd = [fields.get('unit_price_vnd', existing[row['id']].unit_price_vnd if row.get('id') in existing else None)
                  for row, fields in zip(items, values)]
    if all(value is not None for value in prices_vnd):
        subtotal_vnd = sum(value * fields['quantity'] for value, fields in zip(prices_vnd, values))
        if discount > subtotal_vnd:
            return JsonResponse({'error': 'Giảm giá không được vượt quá tổng tiền hàng VND.'}, status=400)
    if order is None:
        order = GatheringOrder(gathering=gathering)
    order.customer_name, order.profile_url, order.paid_amount = name, url, paid
    order.discount_amount = discount
    order.save()
    for row, fields in zip(items, values):
        item = existing.get(row.get('id')) or GatheringItem(order=order)
        for field, value in fields.items():
            setattr(item, field, value)
        item.save()
    order.items.exclude(pk__in=used).filter(pk__in=[int(pk) for pk in existing]).delete()
    return JsonResponse(order_json(order), status=201 if request.method == 'POST' else 200)


@endpoint(['POST'], access='employee')
def gathering_orders(request, pk):
    with transaction.atomic():
        gathering = Gathering.objects.select_for_update().filter(pk=pk).first()
        if gathering is None:
            return JsonResponse({'error': 'Không tìm thấy đợt gom.'}, status=404)
        return save_order(request, gathering)


@endpoint(['PUT', 'DELETE'], access='employee')
def gathering_order_detail(request, pk):
    with transaction.atomic():
        order = GatheringOrder.objects.select_for_update().filter(pk=pk).first()
        if order is None:
            return JsonResponse({'error': 'Không tìm thấy đơn khách.'}, status=404)
        if request.method == 'DELETE':
            order.delete()
            return JsonResponse({'ok': True})
        return save_order(request, order.gathering, order)
