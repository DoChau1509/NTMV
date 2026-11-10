from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drl_app', '0021_populate_organizations'),
    ]

    operations = [
        migrations.AddField(
            model_name='criterion',
            name='is_manual',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='self_submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
