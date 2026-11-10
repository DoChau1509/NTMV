from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('drl_app', '0016_evaluation_score_carry'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='user',
            name='avatar_embedding',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
