from django.db import migrations, models


def backfill_created_at(apps, schema_editor):
    Shipment = apps.get_model('order_app', 'Shipment')
    Shipment.objects.using(schema_editor.connection.alias).update(created_at=models.F('updated_at'))


class Migration(migrations.Migration):
    dependencies = [('order_app', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='shipment', name='created_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_created_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='shipment', name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
