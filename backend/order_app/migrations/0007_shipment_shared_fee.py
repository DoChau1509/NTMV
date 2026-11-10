from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order_app', '0006_shipment_product_details')]
    operations = [
        migrations.AddField(
            model_name='shipment', name='shared_fee',
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
