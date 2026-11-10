import os
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class PdfExporter:
    """
    PDF Report Exporter for Training Points.
    Generates a stylized PDF using ReportLab with Unicode Vietnamese support.
    """
    def export(self, data, parameters):
        # Register standard Windows Arial font for Unicode Vietnamese support
        font_name = 'Helvetica'
        font_bold_name = 'Helvetica-Bold'
        font_italic_name = 'Helvetica-Oblique'
        
        # Windows Fonts path
        win_font_dir = "C:\\Windows\\Fonts"
        arial_ttf = os.path.join(win_font_dir, "arial.ttf")
        arial_bd_ttf = os.path.join(win_font_dir, "arialbd.ttf")
        arial_it_ttf = os.path.join(win_font_dir, "ariali.ttf")
        
        if os.path.exists(arial_ttf):
            try:
                pdfmetrics.registerFont(TTFont('Arial', arial_ttf))
                font_name = 'Arial'
                if os.path.exists(arial_bd_ttf):
                    pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bd_ttf))
                    font_bold_name = 'Arial-Bold'
                else:
                    font_bold_name = 'Arial'
                if os.path.exists(arial_it_ttf):
                    pdfmetrics.registerFont(TTFont('Arial-Italic', arial_it_ttf))
                    font_italic_name = 'Arial-Italic'
                else:
                    font_italic_name = 'Arial'
            except Exception:
                pass

        school_year = parameters.get('school_year', '')
        semester = parameters.get('semester', '')
        faculty = parameters.get('faculty', '')
        class_name = parameters.get('class_name', '')
        
        # Prepare document
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(letter),
            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
        )
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontName=font_bold_name,
            fontSize=16,
            textColor=colors.HexColor('#1F497D'),
            alignment=1, # Center
            spaceAfter=6
        )
        
        sub_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            fontName=font_italic_name,
            fontSize=11,
            alignment=1, # Center
            spaceAfter=15
        )

        header_style = ParagraphStyle(
            'HeaderStyle',
            fontName=font_bold_name,
            fontSize=9,
            textColor=colors.white,
            alignment=1 # Center
        )

        cell_style = ParagraphStyle(
            'CellStyle',
            fontName=font_name,
            fontSize=9,
            alignment=0 # Left
        )

        cell_center_style = ParagraphStyle(
            'CellCenterStyle',
            fontName=font_name,
            fontSize=9,
            alignment=1 # Center
        )
        
        is_audit = len(data) > 0 and 'username' in data[0] and 'action' in data[0]

        if is_audit:
            story.append(Paragraph("BÁO CÁO VẾT HỆ THỐNG (AUDIT LOG)", title_style))
            story.append(Paragraph("Nhật ký chi tiết các thao tác, truy cập và thay đổi cấu hình", sub_style))
            story.append(Spacer(1, 10))
            
            audit_headers = [
                Paragraph("STT", header_style),
                Paragraph("Ngày giờ", header_style),
                Paragraph("Tài khoản", header_style),
                Paragraph("Vai trò", header_style),
                Paragraph("Thao tác", header_style),
                Paragraph("Đối tượng", header_style),
                Paragraph("Giá trị trước", header_style),
                Paragraph("Giá trị sau", header_style),
                Paragraph("Địa chỉ IP", header_style)
            ]
            
            audit_table_data = [audit_headers]
            
            for idx, item in enumerate(data, 1):
                row = [
                    Paragraph(str(idx), cell_center_style),
                    Paragraph(item.get('created_at', ''), cell_center_style),
                    Paragraph(item.get('username', ''), cell_style),
                    Paragraph(item.get('role', ''), cell_center_style),
                    Paragraph(item.get('action', ''), cell_style),
                    Paragraph(item.get('entity_name', ''), cell_style),
                    Paragraph(item.get('before_value', '')[:50] + ('...' if len(item.get('before_value', '')) > 50 else ''), cell_style),
                    Paragraph(item.get('after_value', '')[:50] + ('...' if len(item.get('after_value', '')) > 50 else ''), cell_style),
                    Paragraph(item.get('ip_address', ''), cell_center_style)
                ]
                audit_table_data.append(row)
                
            col_widths = [25, 100, 70, 55, 100, 75, 110, 110, 77]
            t = Table(audit_table_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F497D')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D3D3D3')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
                ('TOPPADDING', (0,1), (-1,-1), 5),
                ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ]))
            story.append(t)
            
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        is_activity = len(data) > 0 and 'activity_title' in data[0]

        if is_activity:
            from reportlab.platypus import PageBreak
            for act_idx, act_data in enumerate(data):
                story.append(Paragraph("BÁO CÁO CHI TIẾT HOẠT ĐỘNG NGOẠI KHÓA", title_style))
                story.append(Paragraph(f"Hoạt động: {act_data.get('activity_title')}", ParagraphStyle(
                    'ActTitle', parent=styles['Normal'], fontName=font_bold_name, fontSize=12, textColor=colors.HexColor('#1F497D'), spaceAfter=4
                )))
                story.append(Paragraph(f"Ngày tổ chức: {act_data.get('activity_date')}  |  Địa điểm: {act_data.get('activity_location')}", sub_style))
                story.append(Spacer(1, 10))
                
                act_headers = [
                    Paragraph("STT", header_style),
                    Paragraph("MSSV", header_style),
                    Paragraph("Họ và tên", header_style),
                    Paragraph("Lớp", header_style),
                    Paragraph("Khoa", header_style),
                    Paragraph("Giờ Check-in", header_style),
                    Paragraph("Giờ Check-out", header_style),
                    Paragraph("Trạng thái", header_style)
                ]
                
                act_table_data = [act_headers]
                
                for idx, p in enumerate(act_data.get('participants', []), 1):
                    status_text = p.get('status', '')
                    if status_text == "Đầy đủ":
                        status_html = f'<font color="#10B981"><b>{status_text}</b></font>'
                    else:
                        status_html = f'<font color="#EF4444"><b>{status_text}</b></font>'
                        
                    row = [
                        Paragraph(str(idx), cell_center_style),
                        Paragraph(p.get('student_id', ''), cell_center_style),
                        Paragraph(p.get('full_name', ''), cell_style),
                        Paragraph(p.get('class_name', ''), cell_center_style),
                        Paragraph(p.get('faculty', ''), cell_style),
                        Paragraph(p.get('checkin_time', ''), cell_center_style),
                        Paragraph(p.get('checkout_time', ''), cell_center_style),
                        Paragraph(status_html, cell_center_style)
                    ]
                    act_table_data.append(row)
                    
                col_widths = [25, 65, 130, 65, 110, 110, 110, 77]
                t = Table(act_table_data, colWidths=col_widths, repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F497D')),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 6),
                    ('TOPPADDING', (0,0), (-1,0), 6),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D3D3D3')),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
                    ('TOPPADDING', (0,1), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,1), (-1,-1), 5),
                ]))
                story.append(t)
                
                if act_idx < len(data) - 1:
                    story.append(PageBreak())
                    
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        # Title & Subtitle paragraphs
        story.append(Paragraph("BÁO CÁO TỔNG HỢP ĐIỂM RÈN LUYỆN SINH VIÊN", title_style))
        
        sub_text = f"Năm học: {school_year}  |  Học kỳ: {semester}"
        filters = []
        if faculty:
            filters.append(f"Khoa: {faculty}")
        if class_name:
            filters.append(f"Lớp: {class_name}")
        if filters:
            sub_text += "  |  " + " - ".join(filters)
        story.append(Paragraph(sub_text, sub_style))
        story.append(Spacer(1, 10))
        
        # Headers definitions
        headers = [
            Paragraph("STT", header_style),
            Paragraph("MSSV", header_style),
            Paragraph("Họ và tên", header_style),
            Paragraph("Lớp", header_style),
            Paragraph("Khoa", header_style),
            Paragraph("GPA", header_style),
            Paragraph("Xếp loại HT", header_style),
            Paragraph("Điểm tự ĐG", header_style),
            Paragraph("Điểm RL tổng", header_style),
            Paragraph("Xếp loại RL", header_style),
            Paragraph("Trạng thái", header_style)
        ]
        
        table_data = [headers]
        
        # Data rows
        for idx, item in enumerate(data, 1):
            row = [
                Paragraph(str(idx), cell_center_style),
                Paragraph(item.get('student_id', ''), cell_center_style),
                Paragraph(item.get('full_name', ''), cell_style),
                Paragraph(item.get('class_name', ''), cell_center_style),
                Paragraph(item.get('faculty', ''), cell_style),
                Paragraph(str(item.get('gpa', 0.0)), cell_center_style),
                Paragraph(item.get('gpa_classification', ''), cell_center_style),
                Paragraph(str(item.get('self_score', 0)), cell_center_style),
                Paragraph(str(item.get('total_score', 0)), cell_center_style),
                Paragraph(item.get('classification', ''), cell_center_style),
                Paragraph(item.get('status', ''), cell_center_style)
            ]
            table_data.append(row)
            
        # Create Table and set Styles
        # Widths must sum up to width of landcape letter minus margins (approx 732 pts)
        col_widths = [25, 60, 110, 60, 80, 40, 70, 55, 60, 80, 92]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F497D')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D3D3D3')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('TOPPADDING', (0,1), (-1,-1), 5),
            ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ]))
        
        story.append(t)
        
        # Build document
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
