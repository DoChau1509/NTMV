from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order_app', '0003_shipment_buyer_name')]
    operations = [migrations.CreateModel(name='OrderContact', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('url', models.URLField(max_length=500, blank=True, default='')),
    ])]
