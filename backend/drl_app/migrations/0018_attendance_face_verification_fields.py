from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('drl_app', '0017_user_avatar_face_embedding'),
    ]

    operations = [
        migrations.AddField(
            model_name='activitycheckin',
            name='face_similarity',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activitycheckin',
            name='face_liveness',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activitycheckin',
            name='face_realness',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activitycheckout',
            name='face_similarity',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activitycheckout',
            name='face_liveness',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activitycheckout',
            name='face_realness',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
