from django.db import migrations, models


def backfill_academic_results(apps, schema_editor):
    Evaluation = apps.get_model("drl_app", "Evaluation")
    TranscriptImportItem = apps.get_model("drl_app", "TranscriptImportItem")

    for evaluation in Evaluation.objects.select_related("student").all():
        item = (
            TranscriptImportItem.objects.filter(
                student=evaluation.student,
                transcript_import__semester=evaluation.semester,
                transcript_import__school_year=evaluation.year,
            )
            .order_by("-transcript_import__uploaded_at", "-id")
            .first()
        )
        if item:
            evaluation.academic_gpa = item.gpa
            evaluation.academic_classification = item.classification
            evaluation.save(update_fields=("academic_gpa", "academic_classification"))


class Migration(migrations.Migration):

    dependencies = [
        ("drl_app", "0014_remove_transcriptimport_source_file_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="academic_gpa",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="academic_classification",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.RunPython(backfill_academic_results, migrations.RunPython.noop),
    ]
