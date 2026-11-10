import { money, paymentStatuses, Shipment } from '../lib/shop';

export default function ShipmentPayment({ item }: { item: Shipment }) {
  // Đơn chưa có dữ liệu thanh toán dùng nhãn mặc định "Chưa cập nhật".
  const status = item.paymentStatus || '';
  return (
    <div className={`shipment-payment payment-${status || 'unknown'}`}>
      <span className="status-badge">{paymentStatuses[status]}</span>
      {(status === 'deposit' || status === 'domestic_shipping' || (item.remainingAmount ?? 0) > 0) && (
        <small>Còn lại: <strong>{money(item.remainingAmount || 0)}</strong></small>
      )}
    </div>
  );
}
