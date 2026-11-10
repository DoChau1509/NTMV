from django.db import migrations, models


def initialize_score_ledger(apps, schema_editor):
    Evaluation = apps.get_model("drl_app", "Evaluation")
    for evaluation in Evaluation.objects.all():
        evaluation.raw_score = evaluation.total_score
        evaluation.base_score = evaluation.total_score
        evaluation.save(update_fields=("raw_score", "base_score"))


class Migration(migrations.Migration):

    dependencies = [
        ("drl_app", "0015_evaluation_academic_result"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="raw_score",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="base_score",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="carry_in",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="carry_out",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="surplus_balance",
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(initialize_score_ledger, migrations.RunPython.noop),
    ]
