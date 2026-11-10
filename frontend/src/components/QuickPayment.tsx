import { FormEvent, useState } from 'react';
import { PaymentStatus, paymentStatuses, Shipment } from '../lib/shop';

export default function QuickPayment({ item, onSave }: { item: Shipment; onSave: (changes: Partial<Shipment>) => void }) {
  const [status, setStatus] = useState<PaymentStatus>(item.paymentStatus || '');
  const [amount, setAmount] = useState(String(item.remainingAmount || ''));
  // Chỉ yêu cầu số tiền còn lại khi khách đang cọc hoặc còn phí ship nội địa.
  const needsAmount = status === 'deposit' || status === 'domestic_shipping';
  const changed = status !== (item.paymentStatus || '') || (needsAmount && Number(amount) !== item.remainingAmount);
  // Gửi bản nháp về trang quản lý; các trạng thái khác đặt số tiền còn lại về 0.
  function submit(e: FormEvent) {
    e.preventDefault();
    onSave({ paymentStatus: status, remainingAmount: needsAmount ? Number(amount) : 0 });
  }
  return (
    <form className="quick-payment" onSubmit={submit}>
      <select aria-label={`Thanh toán ${item.code}`} value={status} onChange={e => setStatus(e.target.value as PaymentStatus)}>
        {Object.entries(paymentStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      {needsAmount && <label>Còn lại (VNĐ)
        <input aria-label={`Số tiền còn lại ${item.code}`} type="number" min="1" max="999999999999" step="1" required value={amount} onChange={e => setAmount(e.target.value)} />
      </label>}
      {changed && <div className="order-row-actions">
        <button type="submit" className="secondary">Lưu</button>
        <button type="button" className="text-button" onClick={() => { setStatus(item.paymentStatus || ''); setAmount(String(item.remainingAmount || '')); }}>Hủy</button>
      </div>}
    </form>
  );
}
