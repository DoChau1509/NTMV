import { FormEvent, useState } from 'react';
import { money, Shipment } from '../lib/shop';

export default function QuickSharedFee({ item, onSave }: { item: Shipment; onSave: (changes: Partial<Shipment>) => void }) {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState(String(item.sharedFee ?? 0));
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({ sharedFee: Number(amount) });
  }
  if (!editing) return <div className="quick-payment">
    <span>{money(item.sharedFee ?? 0)}</span>
    <button type="button" className="text-button" aria-label={`Sửa công chia ${item.code}`} onClick={() => setEditing(true)}>Chỉnh sửa</button>
  </div>;
  return <form className="quick-payment" onSubmit={submit}>
    <label>Công chia (VNĐ)
      <input aria-label={`Công chia ${item.code}`} type="number" required min="0" max="999999999999" step="1" value={amount} onChange={event => setAmount(event.target.value)} />
    </label>
    <div className="order-row-actions">
      <button type="submit" className="secondary">Lưu</button>
      <button type="button" className="text-button" onClick={() => { setAmount(String(item.sharedFee ?? 0)); setEditing(false); }}>Hủy</button>
    </div>
  </form>;
}
