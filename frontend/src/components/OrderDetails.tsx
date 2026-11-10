import { money, paymentStatuses, Shipment, statuses } from '../lib/shop';

export default function OrderDetails({ item }: { item: Shipment }) {
  const amount = (value: number | null | undefined) => value == null ? 'Chưa xác định' : money(value);
  const date = (value?: string) => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : 'Chưa có';
  return <div className="order-details">
    <dl className="order-detail-list">
      <div><dt>Tên hàng</dt><dd>{item.name}</dd></div>
      <div><dt>Người mua</dt><dd>{item.buyerName || 'Chưa có'}</dd></div>
      <div><dt>Mã vận đơn Trung</dt><dd>{item.trackingCode || 'Chưa có'}</dd></div>
      <div><dt>Hành trình</dt><dd>{statuses[item.status]}</dd></div>
      <div><dt>Ngày tạo</dt><dd>{date(item.createdAt)}</dd></div>
      <div><dt>Cập nhật gần nhất</dt><dd>{date(item.updatedAt)}</dd></div>
      <div><dt>Giá tệ</dt><dd>{item.cnyPrice ? `${Number(item.cnyPrice).toLocaleString('vi-VN')} CNY` : 'Chưa có'}</dd></div>
      <div><dt>Tỷ giá chốt / CNY</dt><dd>{amount(item.lockedRate)}</dd></div>
      <div><dt>Tiền hàng quy đổi</dt><dd>{amount(item.baseAmount)}</dd></div>
      <div><dt>Tiền công</dt><dd>{amount(item.laborFee)}</dd></div>
    </dl>
    <h3>Chi tiết phụ phí</h3>
    <dl className="order-detail-list">
      <div><dt>Phí cân</dt><dd>{money(item.weightFeeTotal ?? item.weightFee ?? 0)}</dd></div>
      <div><dt>Phí nội địa</dt><dd>{money(item.domesticFeeTotal ?? item.domesticFee ?? 0)}</dd></div>
      <div><dt>Phí khác / chưa phân loại</dt><dd>{money(item.otherFeeTotal ?? item.surcharge ?? 0)}</dd></div>
      <div><dt>Tổng phụ phí</dt><dd>{money(item.surchargeTotal ?? 0)}</dd></div>
    </dl>
    {item.surchargeNote && <p className="order-detail-note">{item.surchargeNote}</p>}
    <dl className="payment-totals">
      <div><dt>Tổng tiền đơn</dt><dd>{amount(item.totalDue)}</dd></div>
      <div><dt>Đã thanh toán sau hoàn tiền</dt><dd>{money(item.paidAmount ?? 0)}</dd></div>
      <div><dt>Còn cần thanh toán</dt><dd>{item.balance == null ? 'Chưa xác định' : money(item.remainingAmount ?? Math.ceil(Math.max(0, item.balance) / 1000) * 1000)}</dd></div>
      {(item.balance ?? 0) < 0 && <div><dt>Thu dư</dt><dd>{money(-item.balance!)}</dd></div>}
    </dl>
    <p>Trạng thái thanh toán: {paymentStatuses[item.paymentStatus || '']}</p>
    <p className="muted">Tổng tiền = tiền hàng quy đổi + tiền công + phụ phí, làm tròn lên đến 1.000đ. Số còn cần trả cũng làm tròn lên đến 1.000đ; khoản thu/hoàn và công chia giữ nguyên.</p>
    {(item.roundingAdjustment ?? 0) > 0 && <p>Phần làm tròn tổng tiền: +{money(item.roundingAdjustment!)}</p>}
    {!item.paymentCount && <p>Chưa ghi khoản thu nào trong sổ. Nếu khách đã trả tiền trước đây, hãy ghi khoản đó để số còn lại chính xác.</p>}
    <dl className="order-detail-list">
      <div><dt>Công chia</dt><dd>{money(item.sharedFee ?? 0)}</dd></div>
      <div><dt>Thực nhận tiền công</dt><dd>{amount(item.netReceived)}</dd></div>
    </dl>
    {item.productUrl && <a href={item.productUrl} target="_blank" rel="noopener noreferrer">Mở sản phẩm</a>}
    {item.note && <p className="order-detail-note">Ghi chú: {item.note}</p>}
  </div>;
}
