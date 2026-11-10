from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order_app', '0002_shipment_created_at')]
    operations = [migrations.AddField(
        model_name='shipment', name='buyer_name',
        field=models.CharField(max_length=150, blank=True, default=''),
    )]
