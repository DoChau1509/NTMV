export const itemStatuses = { not_bought: 'Chưa mua', bought: 'Đã mua', arrived: 'Đã về', shipped: 'Đã ship' } as const;
export type GatheringItem = {
  id?: string; name: string; note: string; quantity: number; unitPrice: string; unitPriceVnd: number | null; totalCny?: string;
  depositDueOn: string | null;
  status: keyof typeof itemStatuses;
};
export type CustomerOrder = {
  id: string; gatheringId: string; customerName: string; profileUrl: string;
  paidAmount: number; remainingAmount: string | null; discountAmount: number; totalCny: string;
  subtotalVnd: string | null; totalVnd: string | null; items: GatheringItem[]; updatedAt: string;
};
export type Gathering = { id: string; name: string; startsOn: string; endsOn: string; orders: CustomerOrder[] };

export const vietnamDay = (now = new Date()) => new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(now);
export const displayDay = (day: string) => day.split('-').reverse().join('/');
export function deadlineWarning(item: GatheringItem, now = new Date(), remaining: bigint | null = null): string | null {
  if (remaining === 0n || !item.depositDueOn) return null;
  const days = Math.round((Date.parse(`${item.depositDueOn}T00:00:00Z`) - Date.parse(`${vietnamDay(now)}T00:00:00Z`)) / 86400000);
  if (days > 1 || !Number.isFinite(days)) return null;
  const when = days < 0 ? `Quá hạn ${-days} ngày` : days === 0 ? 'Đến hạn hôm nay' : 'Đến hạn ngày mai';
  return `${item.name}: ${when} (${displayDay(item.depositDueOn)}) — đơn khách chưa thanh toán đủ`;
}

// Integer cents keep previews exact, including totals of multiple product lines.
export function lineCents(item: GatheringItem): bigint {
  const value = Number(item.unitPrice);
  if (!item.unitPrice.trim() || !Number.isFinite(value) || value < 0 || value > 9999999999.99 || !Number.isInteger(item.quantity) || item.quantity < 1) return 0n;
  const [whole, fraction] = value.toFixed(2).split('.');
  return (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))) * BigInt(item.quantity);
}
export function formatCny(cents: bigint): string {
  return `¥ ${(cents / 100n).toLocaleString('vi-VN')},${(cents % 100n).toString().padStart(2, '0')}`;
}
export const orderCents = (items: GatheringItem[]) => items.reduce((sum, item) => sum + lineCents(item), 0n);

export function lineVnd(item: GatheringItem): bigint | null {
  if (item.unitPriceVnd == null || !Number.isSafeInteger(item.unitPriceVnd) || item.unitPriceVnd < 0 || item.unitPriceVnd > 1e12 || !Number.isInteger(item.quantity) || item.quantity < 1) return null;
  return BigInt(item.unitPriceVnd) * BigInt(item.quantity);
}

export function orderVnd(items: GatheringItem[], discountAmount = 0): bigint | null {
  if (!Number.isSafeInteger(discountAmount) || discountAmount < 0 || discountAmount > 1e12) return null;
  let total = 0n;
  for (const item of items) {
    const subtotal = lineVnd(item);
    if (subtotal === null) return null;
    total += subtotal;
  }
  return total - BigInt(discountAmount);
}

export function remainingVnd(items: GatheringItem[], discountAmount = 0, paidAmount = 0): bigint | null {
  const total = orderVnd(items, discountAmount);
  if (total === null || total < 0n || !Number.isSafeInteger(paidAmount) || paidAmount < 0 || paidAmount > 1e12) return null;
  const remaining = total - BigInt(paidAmount);
  return remaining > 0n ? remaining : 0n;
}
