from __future__ import annotations

from django.db import transaction

from ..models import AuditLog, ClassInfo, TranscriptImport
from .transcript_matching import build_transcript_preview
from .transcript_parser import parse_transcript_pdf
from .transcript_statistics import build_summary


def validate_transcript_upload(*, uploaded_file, class_info: ClassInfo, school_year: str, semester: str | None, uploaded_by=None):
    parsed = parse_transcript_pdf(uploaded_file, expected_class_name=class_info.name)
    preview_items, class_match = build_transcript_preview(parsed.rows, selected_class=class_info, pdf_class_name=parsed.class_name)
    summary_counts, summary_percent, total = build_summary(preview_items)
    valid = bool(class_match)

    with transaction.atomic():
        import_record = TranscriptImport.objects.create(
            class_info=class_info,
            class_name=class_info.name,
            school_year=school_year or "",
            semester=semester,
            uploaded_by=uploaded_by,
            original_filename=getattr(uploaded_file, "name", ""),
            pdf_class_name=parsed.class_name,
            total_students=total,
            status='VALIDATED',
            preview_data=preview_items,
            summary_data={
                'counts': summary_counts,
                'percentages': summary_percent,
                'valid': valid,
                'class_match': class_match,
            },
        )

        if uploaded_by:
            AuditLog.objects.create(
                user=uploaded_by,
                action="Validate Transcript",
                entity_name="TranscriptImport",
                entity_id=import_record.id,
                before_value="parse_pdf",
                after_value="validated" if valid else "validation_failed",
            )

    return import_record, {
        "valid": valid,
        "class_match": class_match,
        "selected_class": class_info.name,
        "selected_class_id": class_info.id,
        "pdf_class": parsed.class_name,
        "students": preview_items,
        "summary": summary_counts,
        "summary_percent": summary_percent,
        "total_students": total,
        "original_filename": getattr(uploaded_file, "name", ""),
    }
