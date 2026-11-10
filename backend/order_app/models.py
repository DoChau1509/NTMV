from django.contrib.auth.hashers import make_password, check_password
from django.db import models


# Tạo cấu hình mẫu mới cho mỗi bản ghi, tránh dùng chung đối tượng JSON.
def default_pricing():
    return {'rate': 3600, 'tiers': [
        {'from': 0, 'value': 20000, 'type': 'fixed'},
        {'from': 100, 'value': 15000, 'type': 'fixed'},
        {'from': 500, 'value': 10000, 'type': 'fixed'},
    ]}


# Tài khoản admin/nhân viên của hệ thống đặt hàng, tách khỏi tài khoản DRL.
class OrderAccount(models.Model):
    username = models.CharField(max_length=100, unique=True)
    full_name = models.CharField(max_length=150)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=10, choices=[('admin', 'Admin'), ('employee', 'Nhân viên')])
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, password):
        # Lưu hash do Django tạo, không lưu mật khẩu gốc.
        self.password = make_password(password)

    def check_password(self, password):
        return check_password(password, self.password)


# Tỷ giá và các bậc tiền công được lưu chung dưới dạng JSON.
class OrderPricing(models.Model):
    config = models.JSONField(default=default_pricing)
    updated_at = models.DateTimeField(auto_now=True)


# Liên kết liên hệ đặt hàng do admin cấu hình.
class OrderContact(models.Model):
    url = models.URLField(max_length=500, blank=True, default='')


# Mỗi bản ghi là một đơn hàng với vận chuyển và thanh toán được theo dõi riêng.
class Shipment(models.Model):
    payment_status_override = models.CharField(max_length=20, null=True, blank=True, default=None)
    weight_fee = models.PositiveBigIntegerField(default=0)
    domestic_fee = models.PositiveBigIntegerField(default=0)
    surcharge = models.PositiveBigIntegerField(default=0)
    surcharge_note = models.CharField(max_length=500, blank=True, default='')
    pricing_snapshot = models.JSONField(default=dict)
    labor_fee = models.BigIntegerField(null=True, blank=True)
    shared_fee = models.PositiveBigIntegerField(default=0)
    cny_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    product_url = models.URLField(max_length=2000, blank=True, default='')
    payment_status = models.CharField(max_length=20, blank=True, default='', choices=[
        ('', 'Chưa cập nhật'), ('paid', 'Thanh toán đủ'),
        ('deposit', 'Cọc'), ('domestic_shipping', 'Còn phụ phí'),
    ])
    remaining_amount = models.PositiveBigIntegerField(default=0)
    buyer_name = models.CharField(max_length=150, blank=True, default='')
    # Mã đơn là duy nhất; nhiều đơn có thể dùng chung mã vận đơn Trung.
    code = models.CharField(max_length=100, unique=True)
    tracking_code = models.CharField(max_length=100, blank=True, default='')
    name = models.CharField(max_length=200)
    # Giá trị 0–5 tương ứng sáu chặng vận chuyển trong frontend.
    status = models.PositiveSmallIntegerField(default=0)
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ShipmentHistory(models.Model):
    shipment = models.ForeignKey(Shipment, null=True, on_delete=models.SET_NULL, related_name='history')
    code = models.CharField(max_length=100)
    actor = models.CharField(max_length=260)
    action = models.CharField(max_length=20)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class ShipmentPayment(models.Model):
    surcharge_category = models.CharField(max_length=10, default='other', choices=[('weight', 'Phí cân'), ('domestic', 'Phí nội địa'), ('other', 'Phí khác')])
    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name='payments')
    kind = models.CharField(max_length=10, choices=[('receipt', 'Thu tiền'), ('refund', 'Hoàn tiền'), ('surcharge', 'Phụ phí')])
    amount = models.PositiveBigIntegerField()
    paid_at = models.DateTimeField()
    note = models.CharField(max_length=500, blank=True, default='')
    actor = models.CharField(max_length=260)
    created_at = models.DateTimeField(auto_now_add=True)


class Gathering(models.Model):
    name = models.CharField(max_length=200)
    starts_on = models.DateField()
    ends_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)


class GatheringOrder(models.Model):
    gathering = models.ForeignKey(Gathering, on_delete=models.PROTECT, related_name='orders')
    customer_name = models.CharField(max_length=150)
    profile_url = models.URLField(max_length=500, blank=True, default='')
    paid_amount = models.PositiveBigIntegerField(default=0)
    # Legacy stored value; the API now calculates the balance from prices, discount and payments.
    remaining_amount = models.PositiveBigIntegerField(null=True, blank=True, default=None)
    discount_amount = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class GatheringItem(models.Model):
    order = models.ForeignKey(GatheringOrder, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    note = models.TextField(max_length=2000, blank=True, default='')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price_vnd = models.PositiveBigIntegerField(null=True, blank=True, default=None)
    # Retained for existing data; per-item payment status is no longer used by the API or UI.
    payment_status = models.CharField(max_length=10, choices=[
        ('paid', 'Thanh toán đủ'), ('deposit', 'Cọc'), ('weight', 'Còn cân nặng'),
    ], default='deposit')
    deposit_due_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[
        ('not_bought', 'Chưa mua'), ('bought', 'Đã mua'), ('arrived', 'Đã về'), ('shipped', 'Đã ship'),
    ], default='bought')
