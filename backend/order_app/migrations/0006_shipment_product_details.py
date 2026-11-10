from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order_app', '0005_shipment_payment')]
    operations = [
        migrations.AddField(model_name='shipment', name='cny_price', field=models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name='shipment', name='product_url', field=models.URLField(max_length=2000, blank=True, default='')),
    ]
