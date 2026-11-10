import { FormEvent } from "react";
import { ArrowRight, Check, Package, Search, Truck } from "lucide-react";
import { Shipment, statuses } from "../lib/shop";
import ShipmentPayment from "../components/ShipmentPayment";

type Props = {
  code: string;
  setCode: (code: string) => void;
  search: (event: FormEvent) => Promise<void>;
  busy: boolean;
  ready: boolean;
  lookupError: string;
  searchedCode: string | null;
  found: Shipment | undefined;
  lookupItems: Shipment[];
  selectedLookup: string;
  setSelectedLookup: (id: string) => void;
  searching: boolean;
};

export default function ShipmentLookup({
  code,
  setCode,
  search,
  busy,
  ready,
  lookupError,
  searchedCode,
  found,
  lookupItems,
  selectedLookup,
  setSelectedLookup,
  searching,
}: Props) {
  return (
    <section className="tool-card tracking-card" id="tracking">
      <div className="card-heading">
        <span className="tool-icon">
          <Truck size={22} />
        </span>
        <div>
          <span className="eyebrow">02 / TRA CỨU HÀNH TRÌNH</span>
          <h2>Hàng của bạn đến đâu?</h2>
        </div>
      </div>
      <p className="muted">
        Nhập mã đơn Trung hoặc mã vận đơn để kiểm tra trạng thái.
      </p>
      <form onSubmit={search} className="tracking-search">
        <label className="sr-only" htmlFor="tracking-code">
          Mã đơn Trung hoặc mã vận đơn
        </label>
        <Search size={18} />
        <input
          id="tracking-code"
          required
          maxLength={100}
          placeholder="Nhập mã đơn Trung / mã vận đơn..."
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <button className="primary" type="submit" disabled={busy || !ready}>
          Tra cứu <ArrowRight size={15} />
        </button>
      </form>
      {lookupError ? (
        <div className="form-error" role="alert">
          {lookupError}
        </div>
      ) : searching ? (
        <div className="inline-empty" role="status">
          Đang tra cứu...
        </div>
      ) : searchedCode === null ? (
        <div className="tracking-empty">
          <div className="empty-icon">
            <Package size={36} strokeWidth={1.3} />
          </div>
          <h3>Mỗi kiện hàng, một hành trình</h3>
          <p>
            Trạng thái hàng sẽ hiển thị ở đây
            <br />
            sau khi bạn nhập mã đơn Trung.
          </p>
          <div className="mini-route">
            <span>Kho Trung</span>
            <ArrowRight size={15} />
            <span>Kho Việt</span>
            <ArrowRight size={15} />
            <span>Đến tay bạn</span>
          </div>
        </div>
      ) : found ? (
        <div className="tracking-result">
          {/* Cho chọn đơn khi nhiều đơn dùng chung mã vận đơn. */}
          {lookupItems.length > 1 && (
            <label className="lookup-choice">
              Có {lookupItems.length} đơn phù hợp
              <select
                aria-label="Chọn đơn tra cứu"
                value={selectedLookup}
                onChange={(e) => setSelectedLookup(e.target.value)}
              >
                {lookupItems.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code} — {p.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="shipment-title">
            <div>
              <small>{found.code}</small>
              <h3>{found.name}</h3>
              {found.trackingCode && (
                <small>Mã vận đơn: {found.trackingCode}</small>
              )}
            </div>
            <span className="status-badge">{statuses[found.status]}</span>
          </div>
          <div className="lookup-payment">
            <b>Thanh toán</b>
            <ShipmentPayment item={found} />
          </div>
          {/* Các bước trước trạng thái hiện tại được đánh dấu đã hoàn thành. */}
          <ol className="timeline">
            {statuses.map((s, i) => (
              <li
                key={s}
                className={
                  i < found.status
                    ? "complete"
                    : i === found.status
                      ? "current"
                      : ""
                }
              >
                <span className="step-dot">
                  {i <= found.status ? <Check size={12} /> : i + 1}
                </span>
                <div>
                  <b>{s}</b>
                  {i === found.status && <small>Trạng thái hiện tại</small>}
                </div>
              </li>
            ))}
          </ol>
          {found.note && <div className="shipment-note">{found.note}</div>}
          <p className="fine-print">
            Cập nhật: {new Date(found.updatedAt).toLocaleString("vi-VN")}
          </p>
        </div>
      ) : (
        <div className="tracking-empty" role="status">
          <Search size={35} />
          <h3>Chưa tìm thấy mã đơn</h3>
          <p>
            Không có dữ liệu cho “{searchedCode}”.
            <br />
            Vui lòng kiểm tra lại mã hoặc liên hệ nhân viên phụ trách.
          </p>
        </div>
      )}
    </section>
  );
}
