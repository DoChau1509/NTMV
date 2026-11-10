export const statuses = ['Đã mua', 'Có mã đơn Trung', 'Kho Trung', 'Kho Việt', 'Đã kiểm', 'Đã ship hàng'] as const;
export type FeeTier = { from: number; value: number; type: 'fixed' | 'percent' };
export type Settings = { rate: number; tiers: FeeTier[] };
export const paymentStatuses = { '': 'Chưa cập nhật', paid: 'Thanh toán đủ', deposit: 'Cọc', domestic_shipping: 'Còn phụ phí' } as const;
export type PaymentStatus = keyof typeof paymentStatuses;
export type Shipment = { id: string; code: string; trackingCode: string; buyerName?: string; cnyPrice?: string | null; pricingSnapshot?: Settings; lockedRate?: number | null; reprice?: boolean; weightFee?: number; domesticFee?: number; weightFeeTotal?: number; domesticFeeTotal?: number; otherFeeTotal?: number; baseAmount?: number | null; surcharge?: number; surchargeTotal?: number; surchargeNote?: string; totalDue?: number | null; paidAmount?: number; balance?: number | null; paymentCount?: number; laborFee?: number | null; sharedFee?: number; netReceived?: number | null; productUrl?: string; name: string; status: number; paymentStatusOverride?: PaymentStatus | null; rawTotalDue?: number | null; roundingAdjustment?: number | null; paymentStatus?: PaymentStatus; remainingAmount?: number; note: string; createdAt?: string; updatedAt: string };
// Lấy URL đầu tiên từ đoạn chia sẻ sản phẩm và bỏ dấu câu ở cuối link.
export const extractProductUrl = (text: string) => text.match(/https?:\/\/[^\s<>"【】「」]+/i)?.[0].replace(/[.,;!，。；！]+$/, '') || text.trim();
export const defaultSettings: Settings = { rate: 3600, tiers: [{ from: 0, value: 20000, type: 'fixed' }, { from: 100, value: 15000, type: 'fixed' }, { from: 500, value: 10000, type: 'fixed' }] };
export const money = (value: number | bigint) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(value);
// Tỷ giá phải dương; các bậc công tăng dần từ 0 và công phần trăm tối đa 100%.
export function validSettings(s: Settings): boolean {
 return !!s && Number.isFinite(s.rate) && s.rate > 0 && s.rate <= 1e6 && Array.isArray(s.tiers) && s.tiers.length > 0 && s.tiers.every((t,i) => t && Number.isFinite(t.from) && t.from >= 0 && t.from <= 1e9 && (i === 0 ? t.from === 0 : t.from > s.tiers[i-1].from) && Number.isFinite(t.value) && t.value >= 0 && t.value <= (t.type === 'percent' ? 100 : 1e9) && ['fixed','percent'].includes(t.type));
}
// Chọn một bậc công phù hợp, làm tròn tiền hàng và tiền công riêng rồi cộng lại.
export function quote(cny: number, settings: Settings) {
 if (!Number.isFinite(cny) || cny <= 0 || cny > 1e9 || !validSettings(settings)) return null;
 const tier = [...settings.tiers].reverse().find(t => cny >= t.from)!;
 const base = Math.ceil(cny * settings.rate);
 const fee = Math.round(tier.type === 'fixed' ? tier.value : cny * settings.rate * tier.value / 100);
 const total = Math.ceil((base + fee) / 1000) * 1000;
 return { base, fee, total, roundingAdjustment: total - base - fee, tier };
}
// Đồng nhất mã khi nhập, kiểm tra trùng và tra cứu.
export const normalizeCode = (code: string) => code.trim().toUpperCase();
