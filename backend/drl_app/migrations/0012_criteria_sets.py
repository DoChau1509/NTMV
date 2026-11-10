import django.db.models.deletion
from django.db import migrations, models


def create_default_set(apps, schema_editor):
    CriteriaSet = apps.get_model('drl_app', 'CriteriaSet')
    Criterion = apps.get_model('drl_app', 'Criterion')
    Evaluation = apps.get_model('drl_app', 'Evaluation')

    default_set = CriteriaSet.objects.create(
        name='Bộ tiêu chí mặc định',
        description='Bộ tiêu chí được chuyển đổi từ cấu hình hiện có.',
        is_active=True,
    )
    Criterion.objects.filter(criteria_set__isnull=True).update(criteria_set=default_set)
    Evaluation.objects.filter(criteria_set__isnull=True).update(criteria_set=default_set)


class Migration(migrations.Migration):

    dependencies = [
        ('drl_app', '0011_activity_allowed_classes_activity_allowed_clubs_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CriteriaSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('semester', models.CharField(blank=True, max_length=20)),
                ('academic_year', models.CharField(blank=True, max_length=20)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'criteria_set',
                'ordering': ('-is_active', '-created_at'),
            },
        ),
        migrations.AddField(
            model_name='criterion',
            name='criteria_set',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='criteria',
                to='drl_app.criteriaset',
            ),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='criteria_set',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='evaluations',
                to='drl_app.criteriaset',
            ),
        ),
        migrations.AlterField(
            model_name='criterion',
            name='code',
            field=models.CharField(max_length=10),
        ),
        migrations.RunPython(create_default_set, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='criterion',
            name='criteria_set',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='criteria',
                to='drl_app.criteriaset',
            ),
        ),
        migrations.AlterModelOptions(
            name='criterion',
            options={'ordering': ('code',)},
        ),
        migrations.AddConstraint(
            model_name='criterion',
            constraint=models.UniqueConstraint(
                fields=('criteria_set', 'code'),
                name='unique_code_per_criteria_set',
            ),
        ),
    ]
