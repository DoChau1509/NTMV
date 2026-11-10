import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drl_app', '0019_attendance_gps_accuracy'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='max_participants',
            field=models.PositiveIntegerField(
                default=100,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]
