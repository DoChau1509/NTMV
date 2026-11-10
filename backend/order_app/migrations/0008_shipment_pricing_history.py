from decimal import Decimal, ROUND_HALF_UP
from django.db import migrations, models
import django.db.models.deletion


def freeze_existing(apps, schema_editor):
    Shipment = apps.get_model('order_app', 'Shipment')
    Pricing = apps.get_model('order_app', 'OrderPricing')
    History = apps.get_model('order_app', 'ShipmentHistory')
    pricing = Pricing.objects.filter(pk=1).first()
    config = pricing.config if pricing else {'rate': 3600, 'tiers': [
        {'from': 0, 'value': 20000, 'type': 'fixed'},
        {'from': 100, 'value': 15000, 'type': 'fixed'},
        {'from': 500, 'value': 10000, 'type': 'fixed'},
    ]}
    for item in Shipment.objects.all().iterator():
        item.pricing_snapshot = config
        if item.cny_price is not None and item.cny_price > 0:
            tier = next(t for t in reversed(config['tiers']) if item.cny_price >= Decimal(str(t['from'])))
            amount = Decimal(str(tier['value']))
            if tier['type'] == 'percent':
                amount = item.cny_price * Decimal(str(config['rate'])) * amount / 100
            item.labor_fee = int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        item.save(update_fields=['pricing_snapshot', 'labor_fee'])
        History.objects.create(shipment=item, code=item.code, actor='Hệ thống', action='baseline', changes={
            'lockedRate': {'before': None, 'after': config['rate']},
            'laborFee': {'before': None, 'after': item.labor_fee},
        })


class Migration(migrations.Migration):
    dependencies = [('order_app', '0007_shipment_shared_fee')]
    operations = [
        migrations.AddField(model_name='shipment', name='pricing_snapshot', field=models.JSONField(default=dict)),
        migrations.AddField(model_name='shipment', name='labor_fee', field=models.BigIntegerField(blank=True, null=True)),
        migrations.CreateModel(name='ShipmentHistory', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('code', models.CharField(max_length=100)),
            ('actor', models.CharField(max_length=260)),
            ('action', models.CharField(max_length=20)),
            ('changes', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('shipment', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='history', to='order_app.shipment')),
        ]),
        migrations.RunPython(freeze_existing, migrations.RunPython.noop),
    ]
