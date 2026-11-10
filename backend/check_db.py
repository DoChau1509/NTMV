import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from drl_app.models import Organization, Activity

with open("db_info.txt", "w", encoding="utf-8") as f:
    f.write("--- Organizations ---\n")
    for org in Organization.objects.all():
        f.write(f"ID: {org.id}, Name: '{org.name}', Type: '{org.type}'\n")

    f.write("\n--- Activities ---\n")
    for act in Activity.objects.all()[:10]:
        f.write(f"ID: {act.id}, Title: '{act.title}', Organizer: '{act.organizer}'\n")
