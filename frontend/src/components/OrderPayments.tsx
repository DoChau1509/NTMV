import { FormEvent, useEffect, useState } from 'react';
import { api } from '../lib/order-api';
import { money, Shipment } from '../lib/shop';

type Payment = { id: string; kind: string; surchargeCategory?: string; amount: number; paidAt: string; note: string; actor: string };
const categories: Record<string, string> = { weight: 'Phí cân', domestic: 'Phí nội địa', other: 'Phí khác' };
type Result = { shipment: Shipment; items: Payment[] };
const localNow = () => {
  const date = new Date();
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
export default function OrderPayments({ item, onSaved }: { item: Shipment; onSaved: (item: Shipment) => void }) {
  const [data, setData] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState('receipt');
  const [category, setCategory] = useState('weight');
  const [amount, setAmount] = useState('');
  const [paidAt, setPaidAt] = useState(localNow);
  const [note, setNote] = useState('');
  useEffect(() => {
    let active = true;
    api<Result>(`shipments/${item.id}/payments/`).then(result => { if (active) setData(result); })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : 'Không thể tải thanh toán.'); });
    return () => { active = false; };
  }, [item.id]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await api<Result>(`shipments/${item.id}/payments/`, 'POST', { kind, surchargeCategory: kind === 'surcharge' ? category : 'other', amount: Number(amount), paidAt: new Date(paidAt).toISOString(), note });
      setData(result); onSaved(result.shipment); setAmount(''); setNote('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không thể lưu thanh toán.'); }
    finally { setBusy(false); }
  }
  const current = data?.shipment || item;
  return <div className="order-payments">
    {error && <p role="alert" className="form-error">{error}</p>}
    {!data && !error && <p role="status">Đang tải thanh toán...</p>}
    <dl className="payment-totals">
      <div><dt>Tổng phải thu</dt><dd>{current.totalDue == null ? 'Chưa có giá tệ' : money(current.totalDue)}</dd></div>
      <div><dt>Đã thu sau hoàn tiền</dt><dd>{money(current.paidAmount ?? 0)}</dd></div>
      <div><dt>{(current.balance ?? 0) < 0 ? 'Thu dư' : 'Còn cần thanh toán'}</dt><dd>{current.balance == null ? 'Chưa xác định' : money(current.balance < 0 ? -current.balance : current.remainingAmount ?? Math.ceil(current.balance / 1000) * 1000)}</dd></div>
    </dl>
    <p className="muted">Phải thu = tiền hàng theo tỷ giá chốt + tiền công + phụ phí ({money(current.surchargeTotal ?? current.surcharge ?? 0)}). Phụ phí làm tăng phải thu, chưa tính là tiền đã nhận.</p>
    <p className="muted">Tổng tiền và số còn cần trả làm tròn lên đến 1.000đ. Các khoản thu và hoàn tiền giữ đúng số thực tế.</p>
    {data && !data.items.length && <p>Chưa có giao dịch. Nếu đã thu trước đây, hãy ghi số tiền đó vào sổ với ghi chú “Đã thu trước đây”. Khi có giao dịch, trạng thái thanh toán sẽ tự tính theo sổ.</p>}
    <form className="edit-form" onSubmit={submit}>
      <fieldset className="form-lock" disabled={busy || !data || current.totalDue == null}>
        <label>Loại giao dịch<select value={kind} onChange={e => setKind(e.target.value)}><option value="receipt">Thu tiền / cọc</option><option value="refund">Hoàn tiền</option><option value="surcharge">Phụ phí</option></select></label>
        {kind === 'surcharge' && <label>Loại phụ phí<select value={category} onChange={e => setCategory(e.target.value)}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
        <label>Số tiền (VNĐ)<input type="number" required min="1" max="999999999999" step="1" value={amount} onChange={e => setAmount(e.target.value)} /></label>
        <label>Thời điểm thanh toán<input type="datetime-local" required value={paidAt} onChange={e => setPaidAt(e.target.value)} /></label>
        <label>Ghi chú / mã giao dịch<input maxLength={500} value={note} onChange={e => setNote(e.target.value)} /></label>
        <button type="submit" className="primary">{busy ? 'Đang lưu...' : 'Ghi thanh toán'}</button>
      </fieldset>
    </form>
    {data && <ul className="payment-entries">{data.items.map(payment => <li key={payment.id}>
      <strong>{payment.kind === 'surcharge' ? 'Phụ phí +' : payment.kind === 'refund' ? 'Hoàn tiền −' : 'Thu tiền +'}{money(payment.amount)}</strong>
      {payment.kind === 'surcharge' && <span>{categories[payment.surchargeCategory || 'other']}</span>}
      <span>{new Date(payment.paidAt).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })} · {payment.actor}</span>
      {payment.note && <p>{payment.note}</p>}
    </li>)}</ul>}
  </div>;
}
