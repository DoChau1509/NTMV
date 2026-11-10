import json
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from django.core.serializers.json import DjangoJSONEncoder
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

VN = ZoneInfo('Asia/Ho_Chi_Minh')
STATUSES = ['Đã mua', 'Có mã đơn Trung', 'Kho Trung', 'Kho Việt', 'Đã kiểm', 'Đã ship hàng']
PAYMENT_STATUSES = {'': 'Chưa cập nhật', 'paid': 'Thanh toán đủ', 'deposit': 'Cọc', 'domestic_shipping': 'Còn phụ phí'}


def local_date(value):
    return value.astimezone(VN).strftime('%Y-%m-%d %H:%M:%S') if value else ''


def sheet(book, title, headers, rows, money_columns=()):
    page = book.create_sheet(title)
    page.append(headers)
    for row in rows:
        page.append(row)
    for row in page:
        for cell in row:
            # Preserve order codes and untrusted text as literal strings, never formulas.
            if isinstance(cell.value, str):
                cell.value = ILLEGAL_CHARACTERS_RE.sub('�', cell.value)
                cell.data_type = 's'
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    for cell in page[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='24475B')
    page.freeze_panes = 'A2'
    page.auto_filter.ref = page.dimensions
    for index, header in enumerate(headers, 1):
        page.column_dimensions[get_column_letter(index)].width = min(40, max(18, len(header) + 4))
    for column in money_columns:
        for row in page.iter_rows(min_row=2, min_col=column, max_col=column):
            row[0].number_format = '#,##0;[Red]-#,##0'
    return page


def workbook(items, payments, history, metadata, raw_records=()):
    book = Workbook()
    book.remove(book.active)
    sheet(book, 'Thong tin', ['Thông tin', 'Giá trị'], metadata)
    headers = ['ID', 'Mã đơn', 'Mã vận đơn Trung', 'Người mua', 'Tên hàng', 'Hành trình',
               'Thanh toán', 'Chế độ thanh toán', 'Giá tệ (CNY)', 'Tỷ giá chốt', 'Tiền hàng quy đổi',
               'Tiền công', 'Công chia', 'Thực nhận tiền công', 'Phí cân', 'Phí nội địa', 'Phí khác',
               'Tổng phụ phí', 'Tổng trước làm tròn', 'Phần làm tròn', 'Tổng tiền đơn',
               'Đã thu sau hoàn tiền', 'Còn cần thanh toán', 'Thu dư', 'Nội dung phụ phí',
               'Link sản phẩm', 'Ghi chú', 'Ngày tạo (VN)', 'Cập nhật (VN)']
    rows = []
    for item in items:
        rows.append([
            item['id'], item['code'], item['trackingCode'], item['buyerName'], item['name'],
            STATUSES[item['status']], PAYMENT_STATUSES[item['paymentStatus']],
            'Tự động theo sổ' if item['paymentStatusOverride'] is None else 'Chọn thủ công',
            float(item['cnyPrice']) if item['cnyPrice'] is not None else None,
            item['lockedRate'], item['baseAmount'], item['laborFee'], item['sharedFee'], item['netReceived'],
            item['weightFeeTotal'], item['domesticFeeTotal'], item['otherFeeTotal'], item['surchargeTotal'],
            item['rawTotalDue'], item['roundingAdjustment'], item['totalDue'], item['paidAmount'],
            item['remainingAmount'] if item['totalDue'] is not None else None,
            max(0, -item['balance']) if item['balance'] is not None else None,
            item['surchargeNote'], item['productUrl'], item['note'],
            local_date(datetime.fromisoformat(item['createdAt'])),
            local_date(datetime.fromisoformat(item['updatedAt'])),
        ])
    page = sheet(book, 'Don hang', headers, rows, range(10, 25))
    for row in page.iter_rows(min_row=2, min_col=9, max_col=9):
        row[0].number_format = '#,##0.00'
    totals = [None] * len(headers)
    totals[0] = 'TỔNG'
    totals[4] = f'{len(items)} đơn; {sum(i["totalDue"] is None for i in items)} đơn chưa xác định tổng tiền'
    for column in range(12, 25):
        totals[column - 1] = sum(row[column - 1] or 0 for row in rows)
    page.append(totals)
    for cell in page[page.max_row]:
        cell.font = Font(bold=True, color='17654E')
        cell.fill = PatternFill('solid', fgColor='EDF7F1')
        cell.number_format = '#,##0;[Red]-#,##0'
    # The summary is outside the filter so it cannot be sorted into the order rows.
    page.auto_filter.ref = f'A1:AC{len(items) + 1}'
    sheet(book, 'Thanh toan', ['ID', 'ID đơn', 'Mã đơn', 'Loại giao dịch', 'Loại phụ phí', 'Số tiền (VNĐ)',
                             'Thời điểm thanh toán (VN)', 'Ghi chú', 'Người ghi', 'Ngày ghi (VN)'], [
        [str(p.pk), str(p.shipment_id), p.shipment.code,
         {'receipt': 'Thu tiền / cọc', 'refund': 'Hoàn tiền', 'surcharge': 'Phụ phí'}[p.kind],
         {'weight': 'Phí cân', 'domestic': 'Phí nội địa', 'other': 'Phí khác'}[p.surcharge_category] if p.kind == 'surcharge' else '',
         p.amount, local_date(p.paid_at), p.note, p.actor, local_date(p.created_at)] for p in payments
    ], [6])
    sheet(book, 'Lich su', ['ID', 'ID đơn', 'Mã đơn', 'Thao tác', 'Người thực hiện', 'Thời điểm (VN)', 'Trường', 'Trước', 'Sau'], [
        [str(entry.pk), str(entry.shipment_id or ''), entry.code, entry.action, entry.actor,
         local_date(entry.created_at), field,
         json.dumps(change.get('before'), ensure_ascii=False, cls=DjangoJSONEncoder),
         json.dumps(change.get('after'), ensure_ascii=False, cls=DjangoJSONEncoder)]
        for entry in history for field, change in entry.changes.items()
    ])
    if raw_records:
        raw_rows = []
        for model, pk, values in raw_records:
            payload = json.dumps(values, cls=DjangoJSONEncoder, ensure_ascii=True)
            # Excel limits a cell to 32,767 characters. Keep every byte of large records.
            for index in range(0, len(payload), 30000):
                raw_rows.append([model, str(pk), index // 30000 + 1, payload[index:index + 30000]])
        sheet(book, 'Du lieu sao luu', ['Loại dữ liệu', 'ID', 'Phần', 'Dữ liệu JSON'], raw_rows)
    output = BytesIO()
    book.save(output)
    return output.getvalue()
