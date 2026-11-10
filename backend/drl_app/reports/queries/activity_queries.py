from datetime import datetime
from ...models import Activity, ActivityParticipant, ActivityCheckIn, ActivityCheckOut

class ActivityQueries:
    """
    Query execution for Activity reports.
    Groups participants by activity and retrieves checkin/checkout timestamps.
    """
    def execute(self, parameters):
        school_year = parameters.get('school_year')
        semester = parameters.get('semester')
        
        activity_queryset = Activity.objects.all()
        
        if school_year and semester:
            try:
                parts = school_year.split('-')
                year_start = int(parts[0])
                year_end = int(parts[1])
            except Exception:
                year_start = 2025
                year_end = 2026
                
            if semester == 'HK1':
                start_date = f"{year_start}-08-01"
                end_date = f"{year_start}-12-31"
            elif semester == 'HK2':
                start_date = f"{year_end}-01-01"
                end_date = f"{year_end}-03-31"
            else: # HK3
                start_date = f"{year_end}-04-01"
                end_date = f"{year_end}-07-31"
                
            activity_queryset = activity_queryset.filter(date__range=[start_date, end_date])
            
        results = []
        for act in activity_queryset.order_by('date', 'id'):
            participants = ActivityParticipant.objects.filter(activity=act).select_related('student', 'student__class_info')
            
            # Fetch checkins and checkouts for this activity
            checkins = {c.student_id: c.check_in_time for c in ActivityCheckIn.objects.filter(activity=act)}
            checkouts = {c.student_id: c.check_out_time for c in ActivityCheckOut.objects.filter(activity=act)}
            
            participant_list = []
            for p in participants:
                student = p.student
                c_in = checkins.get(student.id)
                c_out = checkouts.get(student.id)
                
                # Format time strings
                c_in_str = c_in.strftime('%H:%M:%S %d/%m/%Y') if c_in else ''
                c_out_str = c_out.strftime('%H:%M:%S %d/%m/%Y') if c_out else ''
                
                status_str = "Đầy đủ" if (c_in and c_out) else "Thiếu"
                
                participant_list.append({
                    'student_id': student.student_id,
                    'full_name': student.full_name,
                    'class_name': student.class_info.name if student.class_info else '',
                    'faculty': student.faculty or '',
                    'checkin_time': c_in_str,
                    'checkout_time': c_out_str,
                    'status': status_str
                })
                
            results.append({
                'activity_id': act.id,
                'activity_title': act.title,
                'activity_date': act.date.strftime('%d/%m/%Y') if act.date else '',
                'activity_location': act.location or 'ITC',
                'participants': participant_list
            })
            
        return results
