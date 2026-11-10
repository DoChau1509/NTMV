from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order_app', '0004_ordercontact')]
    operations = [
        migrations.AddField(
            model_name='shipment', name='payment_status',
            field=models.CharField(blank=True, default='', max_length=20, choices=[
                ('', 'Chưa cập nhật'), ('paid', 'Thanh toán đủ'),
                ('deposit', 'Cọc'), ('domestic_shipping', 'Còn ship nội địa'),
            ]),
        ),
        migrations.AddField(
            model_name='shipment', name='remaining_amount',
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
