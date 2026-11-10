from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order_app', '0016_gathering_vnd_prices_and_discount'),
    ]

    operations = [
        migrations.AddField(
            model_name='gatheringitem',
            name='note',
            field=models.TextField(blank=True, default='', max_length=2000),
        ),
    ]
