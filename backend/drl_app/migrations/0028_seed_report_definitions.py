from django.db import migrations

def seed_report_definitions(apps, schema_editor):
    ReportDefinition = apps.get_model('drl_app', 'ReportDefinition')
    
    definitions = [
        {
            "code": "evaluation_summary",
            "name": "Báo cáo tổng hợp điểm rèn luyện",
            "description": "Tổng hợp điểm rèn luyện của sinh viên theo học kỳ và năm học.",
            "module": "evaluation",
            "category": "Báo cáo Điểm rèn luyện",
            "permission_required": "advisor"
        },
        {
            "code": "activity_summary",
            "name": "Tổng hợp hoạt động ngoại khóa",
            "description": "Danh sách hoạt động và số lượng sinh viên đăng ký tham gia.",
            "module": "activity",
            "category": "Báo cáo Hoạt động",
            "permission_required": "advisor"
        },
        {
            "code": "audit_report",
            "name": "Báo cáo vết hệ thống (Audit Log)",
            "description": "Lịch sử thao tác, truy cập và thay đổi cấu hình hệ thống.",
            "module": "audit",
            "category": "Báo cáo Hệ thống",
            "permission_required": "admin"
        }
    ]

    active_codes = [d["code"] for d in definitions]
    ReportDefinition.objects.exclude(code__in=active_codes).delete()

    for d in definitions:
        ReportDefinition.objects.update_or_create(
            code=d["code"],
            defaults={
                "name": d["name"],
                "description": d["description"],
                "module": d["module"],
                "category": d["category"],
                "permission_required": d["permission_required"],
                "is_active": True
            }
        )

def remove_report_definitions(apps, schema_editor):
    ReportDefinition = apps.get_model('drl_app', 'ReportDefinition')
    ReportDefinition.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('drl_app', '0027_reportdefinition_reportjob'),
    ]

    operations = [
        migrations.RunPython(seed_report_definitions, remove_report_definitions),
    ]
