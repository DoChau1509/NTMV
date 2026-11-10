from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order_app', '0014_gatheringorder_remaining_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gatheringitem',
            name='status',
            field=models.CharField(
                choices=[('not_bought', 'Chưa mua'), ('bought', 'Đã mua'), ('arrived', 'Đã về'), ('shipped', 'Đã ship')],
                default='bought',
                max_length=10,
            ),
        ),
    ]
