from ...models import Evaluation, Student

class EvaluationQueries:
    """
    Query execution for DRL (Evaluation) reports.
    Supports filtering by year, semester, faculty, and class.
    """
    def execute(self, parameters):
        school_year = parameters.get('school_year')
        semester = parameters.get('semester')
        faculty = parameters.get('faculty')
        class_name = parameters.get('class_name')

        student_queryset = Student.objects.all()

        if faculty:
            student_queryset = student_queryset.filter(faculty__iexact=faculty.strip())
        if class_name:
            classes = [c.strip() for c in class_name.split(',') if c.strip()]
            if len(classes) > 1:
                student_queryset = student_queryset.filter(class_info__name__in=classes)
            elif classes:
                student_queryset = student_queryset.filter(class_info__name__iexact=classes[0])

        student_queryset = student_queryset.select_related('class_info').order_by('class_info__name', 'student_id')

        student_ids = [s.id for s in student_queryset]
        evaluations_dict = {}
        if student_ids and school_year and semester:
            evals = Evaluation.objects.filter(
                student_id__in=student_ids,
                year=school_year,
                semester=semester
            )
            for ev in evals:
                evaluations_dict[ev.student_id] = ev

        results = []
        for student in student_queryset:
            eval_obj = evaluations_dict.get(student.id)
            
            gpa = float(eval_obj.academic_gpa) if (eval_obj and eval_obj.academic_gpa is not None) else 0.0
            gpa_classification = eval_obj.academic_classification if (eval_obj and eval_obj.academic_classification) else ''
            self_score = eval_obj.base_score if eval_obj else 0
            total_score = eval_obj.total_score if eval_obj else 0
            classification = eval_obj.classification if (eval_obj and eval_obj.classification) else ''
            
            missing = []
            if not eval_obj:
                missing.append("Chưa tự đánh giá")
                missing.append("Thiếu GPA")
            else:
                if eval_obj.academic_gpa is None:
                    missing.append("Thiếu GPA")
                if not eval_obj.academic_classification:
                    missing.append("Thiếu xếp loại học tập")
                if eval_obj.status == 'draft':
                    missing.append("Chưa nộp đánh giá")
                    
            status_text = "Đầy đủ" if not missing else "Thiếu: " + ", ".join(missing)

            results.append({
                'student_id': student.student_id,
                'full_name': student.full_name,
                'class_name': student.class_info.name if student.class_info else '',
                'faculty': student.faculty or '',
                'gpa': gpa,
                'gpa_classification': gpa_classification or 'Chưa xếp loại',
                'self_score': self_score,
                'total_score': total_score,
                'classification': classification or 'Chưa xếp loại',
                'status': status_text
            })
        return results
