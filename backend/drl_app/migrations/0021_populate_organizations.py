from django.db import migrations


PLACEHOLDER_NAMES = {
    '',
    'admin',
    'đơn vị tổ chức',
    'don vi to chuc',
}
FALLBACK_NAME = 'Chưa cập nhật đơn vị'


def populate_organizations(apps, schema_editor):
    Organization = apps.get_model('drl_app', 'Organization')
    Activity = apps.get_model('drl_app', 'Activity')
    ExternalActivity = apps.get_model('drl_app', 'ExternalActivity')

    fallback, _ = Organization.objects.get_or_create(
        name=FALLBACK_NAME,
        defaults={'type': 'Khác'},
    )

    for activity in Activity.objects.all().iterator():
        name = (activity.organizer or '').strip()
        if name.casefold() in PLACEHOLDER_NAMES:
            if activity.organizer != fallback.name:
                activity.organizer = fallback.name
                activity.save(update_fields=['organizer'])
            continue
        Organization.objects.get_or_create(
            name=name,
            defaults={'type': 'Đơn vị nội bộ'},
        )

    for activity in ExternalActivity.objects.all().iterator():
        name = (activity.organizer_name or '').strip()
        if name.casefold() in PLACEHOLDER_NAMES:
            if activity.organizer_name != fallback.name:
                activity.organizer_name = fallback.name
                activity.save(update_fields=['organizer_name'])
            continue
        Organization.objects.get_or_create(
            name=name,
            defaults={'type': 'Đơn vị ngoài trường'},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('drl_app', '0020_activity_max_participants'),
    ]

    operations = [
        migrations.RunPython(populate_organizations, migrations.RunPython.noop),
    ]
