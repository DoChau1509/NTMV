import { useEffect, useState } from 'react';
import { api } from '../lib/order-api';
import { money, paymentStatuses, Settings, statuses } from '../lib/shop';

type Entry = { id: string; actor: string; action: string; changes: Record<string, { before: unknown; after: unknown }>; createdAt: string };
const fields: Record<string, string> = { surcharge: 'Phụ phí', surchargeNote: 'Nội dung phụ phí', totalDue: 'Tổng phải thu', paidAmount: 'Đã thu', balance: 'Còn thiếu / thu dư', paymentCount: 'Số giao dịch', paymentReceipt: 'Thu tiền', paymentRefund: 'Hoàn tiền', code: 'Mã đơn', trackingCode: 'Mã vận đơn Trung', buyerName: 'Người mua', name: 'Tên hàng', status: 'Hành trình', paymentStatus: 'Thanh toán', remainingAmount: 'Còn lại', cnyPrice: 'Giá tệ', productUrl: 'Link sản phẩm', note: 'Ghi chú', sharedFee: 'Công chia', laborFee: 'Tiền công', lockedRate: 'Tỷ giá chốt', pricingSnapshot: 'Bảng giá chốt' };
fields.paymentSurcharge = 'Ghi phụ phí';
fields.surchargeTotal = 'Tổng phụ phí';
fields.weightFee = 'Phí cân trong đơn';
fields.domesticFee = 'Phí nội địa trong đơn';
fields.weightFeeTotal = 'Tổng phí cân';
fields.domesticFeeTotal = 'Tổng phí nội địa';
fields.otherFeeTotal = 'Tổng phí khác';
fields.baseAmount = 'Tiền hàng quy đổi';
fields.surchargeCategory = 'Loại phụ phí';
fields.paymentStatusOverride = 'Trạng thái thanh toán được chọn';
fields.rawTotalDue = 'Tổng tiền trước làm tròn';
fields.roundingAdjustment = 'Phần làm tròn tổng tiền';
function display(key: string, value: unknown): string {
  if (key === 'paymentStatusOverride') return value == null ? 'Tự động theo sổ' : paymentStatuses[value as keyof typeof paymentStatuses] || String(value);
  if (value === null || value === undefined || value === '') return 'Chưa có';
  if (key === 'surchargeCategory') return ({ weight: 'Phí cân', domestic: 'Phí nội địa', other: 'Phí khác' } as Record<string, string>)[String(value)] || String(value);
  if (['weightFee', 'domesticFee', 'weightFeeTotal', 'domesticFeeTotal', 'otherFeeTotal', 'baseAmount'].includes(key)) return money(Number(value));
  if (key === 'paymentSurcharge' || key === 'surchargeTotal') return money(Number(value));
  if (key === 'rawTotalDue' || key === 'roundingAdjustment') return money(Number(value));
  if (key === 'status') return statuses[Number(value)] || String(value);
  if (key === 'paymentStatus') return paymentStatuses[value as keyof typeof paymentStatuses] || String(value);
  if (['remainingAmount', 'sharedFee', 'laborFee', 'lockedRate', 'surcharge', 'totalDue', 'paidAmount', 'balance', 'paymentReceipt', 'paymentRefund'].includes(key)) return money(Number(value));
  return String(value);
}

export default function OrderHistory({ id, code, version }: { id: string; code: string; version: string }) {
  const [items, setItems] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api<{ items: Entry[] }>(`shipments/${id}/history/`)
      .then(data => { if (active) setItems(data.items); })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : 'Không thể tải lịch sử.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, version]);
  return <section className="order-history" aria-label={`Lịch sử ${code}`}>
    <h3>Lịch sử cập nhật · {code}</h3>
    {loading ? <p role="status">Đang tải lịch sử...</p> : error ? <p role="alert">{error}</p> : !items.length ? <p>Chưa có lịch sử cập nhật.</p> : <ol>
      {items.map(entry => <li key={entry.id}>
        <div><strong>{({ create: 'Tạo đơn', update: 'Cập nhật đơn', baseline: 'Chốt giá cho đơn cũ', delete: 'Xóa đơn' } as Record<string, string>)[entry.action] || entry.action}</strong> · {entry.actor}</div>
        <time dateTime={entry.createdAt}>{new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date(entry.createdAt))}</time>
        {entry.action === 'baseline' && <p>Chốt theo bảng giá tại thời điểm bổ sung tính năng, chưa có dữ liệu lịch sử trước đó.</p>}
        <ul>{Object.entries(entry.changes).filter(([key]) => key !== 'pricingSnapshot').map(([key, change]) => <li key={key}><b>{fields[key] || key}:</b> {display(key, change.before)} → {display(key, change.after)}</li>)}</ul>
        {entry.changes.pricingSnapshot?.after != null && <details><summary>Bảng giá đã chốt</summary>
          <p>1 CNY = {money((entry.changes.pricingSnapshot.after as Settings).rate)}</p>
          <ul>{(entry.changes.pricingSnapshot.after as Settings).tiers.map((tier, index) => <li key={index}>Từ {tier.from.toLocaleString('vi-VN')} CNY: {tier.type === 'fixed' ? money(tier.value) : `${tier.value}% tiền hàng`}</li>)}</ul>
        </details>}
      </li>)}
    </ol>}
  </section>;
}
