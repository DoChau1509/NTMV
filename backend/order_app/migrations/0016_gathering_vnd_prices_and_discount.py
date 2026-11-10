from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order_app', '0015_alter_gatheringitem_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='gatheringorder',
            name='discount_amount',
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='gatheringitem',
            name='unit_price_vnd',
            field=models.PositiveBigIntegerField(blank=True, default=None, null=True),
        ),
    ]
