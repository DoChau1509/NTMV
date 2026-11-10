from collections import Counter

from ..models import Student
from .transcript_statistics import classify_gpa


def match_student(student_code: str):
    return Student.objects.filter(student_id=student_code).first()


def detect_duplicate_codes(rows):
    counts = Counter(row.student_code for row in rows)
    return {code for code, count in counts.items() if count > 1}


def build_transcript_preview(rows, selected_class=None, pdf_class_name: str = ""):
    duplicate_codes = detect_duplicate_codes(rows)
    class_match = True
    if selected_class and pdf_class_name:
        class_match = selected_class.name.strip().upper() == pdf_class_name.strip().upper()

    items = []
    for row in rows:
        student = match_student(row.student_code)
        classification = classify_gpa(row.gpa)
        match_status = "MATCHED"
        remark = ""
        display_name = student.full_name if student else (row.full_name or "")

        if not class_match:
            match_status = "CLASS_MISMATCH"
            remark = f"PDF thuộc lớp {pdf_class_name} nhưng đang chọn lớp {selected_class.name if selected_class else ''}"
        elif row.student_code in duplicate_codes:
            match_status = "DUPLICATE"
            remark = "MSSV bị trùng trong file PDF"
        elif not student:
            match_status = "NOT_FOUND"
            remark = "Không tìm thấy sinh viên trong database"

        items.append({
            "student_db_id": student.id if student else None,
            "student_id": student.student_id if student else "",
            "student_code": row.student_code,
            "full_name": display_name,
            "gpa": float(row.gpa),
            "classification": classification,
            "match_status": match_status,
            "remark": remark,
            "status": match_status,
        })

    return items, class_match
