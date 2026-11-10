import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from drl_app.models import Activity, ActivityParticipant

class Command(BaseCommand):
    help = 'Gửi email nhắc nhở cho sinh viên về các hoạt động ngoại khóa diễn ra vào ngày mai.'

    def handle(self, *args, **options):
        now = timezone.now()
        tomorrow_date = (now + datetime.timedelta(days=1)).date()
        
        # Tìm tất cả hoạt động có date = tomorrow_date
        activities = Activity.objects.filter(date=tomorrow_date, status='upcoming')
        
        self.stdout.write(f"Tìm thấy {activities.count()} hoạt động diễn ra vào ngày {tomorrow_date}")
        
        for activity in activities:
            # Tìm sinh viên đã đăng ký tham gia hoạt động này
            participants = ActivityParticipant.objects.filter(activity=activity, status='registered')
            
            for participant in participants:
                student = participant.student
                if not student.email:
                    continue
                
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    
                    time_str = activity.start_time.strftime("%H:%M") if activity.start_time else "Chưa cấu hình"
                    location_str = activity.location or (activity.room.name if activity.room else "Chưa cấu hình")
                    
                    email_subject = f"[ITC Point] Nhắc nhở: Hoạt động '{activity.title}' diễn ra vào ngày mai"
                    email_message = (
                        f"Chào {student.full_name},\n\n"
                        f"Hệ thống nhắc nhở bạn có lịch tham gia hoạt động '{activity.title}' vào ngày mai ({tomorrow_date}).\n\n"
                        f"Thời gian bắt đầu: {time_str}\n"
                        f"Địa điểm: {location_str}\n"
                        f"Điểm rèn luyện dự kiến: +{activity.points}đ.\n\n"
                        f"Vui lòng đến đúng giờ và thực hiện điểm danh Face ID khi tham gia."
                    )
                    
                    email_html = f"""
<div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); background-color: #ffffff;">
  <div style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); padding: 32px 24px; text-align: center; color: white;">
    <h1 style="margin: 0; font-size: 24px; font-weight: 800;">Nhắc Nhở Lịch Hoạt Động</h1>
    <p style="margin: 4px 0 0 0; font-size: 13px; color: rgba(255,255,255,0.85); font-weight: 500;">Sự kiện diễn ra vào ngày mai ({tomorrow_date})</p>
  </div>
  <div style="padding: 40px 32px; background-color: #ffffff;">
    <h2 style="margin-top: 0; color: #1e293b; font-size: 20px; font-weight: 700;">Chào {student.full_name},</h2>
    <p style="color: #475569; line-height: 1.6; font-size: 15px;">Bạn có lịch tham gia hoạt động ngoại khóa dưới đây vào ngày mai. Vui lòng sắp xếp thời gian để tham gia đầy đủ:</p>
    
    <div style="background-color: #f8fafc; border-radius: 12px; padding: 20px; margin: 28px 0; border: 1px solid #f1f5f9; border-left: 4px solid #3b82f6;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; width: 150px; text-transform: uppercase;">Hoạt động:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: 700;">{activity.title}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase;">Thời gian:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: 500;">{time_str} - {tomorrow_date.strftime("%d/%m/%Y")}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase;">Địa điểm:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: 500;">{location_str}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase;">Điểm DRL:</td>
          <td style="padding: 8px 0; font-size: 15px; color: #10b981; font-weight: 700;">+{activity.points} điểm</td>
        </tr>
      </table>
    </div>

    <div style="background-color: #eff6ff; border-radius: 8px; padding: 14px 18px; border: 1px solid #dbeafe;">
      <p style="color: #1e40af; font-size: 13px; font-weight: 600; margin: 0; line-height: 1.5;">
        * Hướng dẫn: Đừng quên mở ứng dụng quét khuôn mặt (Face ID) khi check-in và check-out tại địa điểm tổ chức để được tính điểm rèn luyện.
      </p>
    </div>
  </div>
  <div style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #f1f5f9; color: #94a3b8; font-size: 12px;">
    <p style="margin: 0 0 6px 0; font-weight: 500;">Email này được hệ thống ITC Point gửi tự động.</p>
    <p style="margin: 0;">© 2026 ITC Point. All rights reserved.</p>
  </div>
</div>
"""
                    send_mail(
                        email_subject,
                        email_message,
                        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@itcpoint.com'),
                        [student.email],
                        fail_silently=True,
                        html_message=email_html
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Lỗi gửi email cho sinh viên {student.student_id}: {e}"))
