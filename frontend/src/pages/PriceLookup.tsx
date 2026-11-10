import { useState } from "react";
import { ArrowDownUp, Check, Pencil, Settings2 } from "lucide-react";
import { money, quote, Settings } from "../lib/shop";
import OrderContact from "../components/OrderContact";

type Props = {
    isAdmin: boolean;
    settings: Settings;
    ready: boolean;
    busy: boolean;
    canEdit: boolean;
    onEdit: () => void;
};

export default function PriceLookup({
    isAdmin,
    settings,
    ready,
    busy,
    canEdit,
    onEdit,
}: Props) {
    const [amount, setAmount] = useState("100");
    // Tính lại báo giá khi số tệ thay đổi, sau khi tải được tỷ giá từ máy chủ.
    const result = ready ? quote(Number(amount), settings) : null;
    return (
        <section className="tool-card" id="pricing">
            <div className="card-heading">
                <span className="tool-icon">
                    <ArrowDownUp size={22} />
                </span>
                <div>
                    <span className="eyebrow">01 / BÁO GIÁ</span>
                    <h2>Tra giá sản phẩm</h2>
                </div>
                {canEdit && (
                    <button
                        disabled={busy}
                        className="icon-button"
                        aria-label="Chỉnh tỷ giá và thang tiền công"
                        onClick={onEdit}
                    >
                        <Settings2 size={20} />
                    </button>
                )}
            </div>
            <p className="muted">Nhập số tệ để xem ngay giá.</p>
            <label className="field-label" htmlFor="cny">
                Số tiền Nhân dân tệ
            </label>
            <div className="amount-field">
                <input
                    id="cny"
                    disabled={!ready}
                    type="number"
                    min="0.01"
                    max="1000000000"
                    step="0.01"
                    placeholder="Nhập số tiền"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                />
                <span>¥ CNY</span>
            </div>
            <div className="rate-summary">
                <span>
                    1 CNY = <b>{ready ? money(settings.rate) : "—"}</b>
                </span>
                {canEdit && (
                    <button disabled={busy} onClick={onEdit}>
                        Thay đổi <Pencil size={11} />
                    </button>
                )}
            </div>
            {result ? (
                <>
                    <div className="breakdown">
                        <div>
                            <span>Tiền hàng quy đổi</span>
                            <b>{money(result.base)}</b>
                        </div>
                        <div>
                            <span>
                                Tiền công{" "}
                                {result.tier.type === "percent"
                                    ? `(${result.tier.value}%)`
                                    : ""}
                            </span>
                            <b>+ {money(result.fee)}</b>
                        </div>
                        {result.roundingAdjustment > 0 && <div><span>Làm tròn lên đến 1.000đ</span><b>+ {money(result.roundingAdjustment)}</b></div>}
                    </div>
                    <div className="quote-total">
                        <span>
                            GIÁ SẢN PHẨM
                            <strong data-testid="quote-total">{money(result.total)}</strong>
                        </span>
                        <span className="total-check">
                            <Check size={20} />
                        </span>
                    </div>
                    <p className="fine-print">
                        Giá trên đã gồm tiền công. Chưa bao gồm phí vận chuyển và các phụ
                        phí khác.
                    </p>
                </>
            ) : (
                <div className="inline-empty">
                    {ready
                        ? "Nhập số tiền lớn hơn 0, tối đa 1 tỷ CNY để tra giá."
                        : "Chưa có dữ liệu tỷ giá từ máy chủ."}
                </div>
            )}
            {/* Hiển thị khoảng áp dụng và mức công của từng bậc đang dùng. */}
            {ready && (
                <details className="fee-details">
                    <summary>Thang tiền công đang áp dụng</summary>
                    <div className="tier-list">
                        {settings.tiers.map((t, i) => (
                            <div key={i}>
                                <span>
                                    {t.from.toLocaleString("vi-VN")}{" "}
                                    {settings.tiers[i + 1]
                                        ? `đến dưới ${settings.tiers[i + 1].from.toLocaleString("vi-VN")}`
                                        : "trở lên"}{" "}
                                    CNY
                                </span>
                                <b>
                                    {t.type === "fixed"
                                        ? money(t.value)
                                        : `${t.value}% tiền hàng`}
                                </b>
                            </div>
                        ))}
                    </div>
                    <p className="fine-print">
                        Chọn đúng một bậc theo tổng số tệ đã nhập, không cộng dồn các bậc.
                    </p>
                </details>
            )}
            <OrderContact isAdmin={isAdmin} />
        </section>
    );
}
