from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('drl_app', '0018_attendance_face_verification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='activitycheckin',
            name='gps_accuracy',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activitycheckout',
            name='gps_accuracy',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
