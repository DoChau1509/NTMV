import { FormEvent, useEffect, useState } from "react";
import { Check, Download, History, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { api, downloadOrderFile } from "../lib/order-api";
import { extractProductUrl, money, Settings, normalizeCode, PaymentStatus, paymentStatuses, Shipment, statuses } from "../lib/shop";
import OrderDetails from "../components/OrderDetails";
import OrderHistory from "../components/OrderHistory";
import OrderPayments from "../components/OrderPayments";
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogClose } from "../components/ui/dialog";

// Giá trị khởi tạo cho biểu mẫu thêm đơn hàng.
const blank: Shipment = {
  id: "",
  code: "",
  trackingCode: "",
  buyerName: "",
  cnyPrice: '',
  sharedFee: 0,
  productUrl: '',
  name: "",
  status: 0,
  paymentStatus: '',
  remainingAmount: 0,
  note: "",
  updatedAt: "",
};
export default function OrderManagement({
  onChange,
  settings,
}: {
  onChange: (item: Shipment, removed?: boolean) => void;
  settings?: Settings;
}) {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [manageQuery, setManageQuery] = useState("");
  const [currentMonth] = useState(() =>
    new Intl.DateTimeFormat("sv-SE", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
    }).format(new Date()),
  );
  const [filterMonth, setFilterMonth] = useState(currentMonth.slice(5));
  const [filterYear, setFilterYear] = useState(currentMonth.slice(0, 4));
  const [draft, setDraft] = useState<Shipment>(blank);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [historyId, setHistoryId] = useState<string | null>(null);
  const historyItem = shipments.find(item => item.id === historyId);
  const [paymentId, setPaymentId] = useState<string | null>(null);
  const paymentItem = shipments.find(item => item.id === paymentId);
  const [detailId, setDetailId] = useState<string | null>(null);
  const detailItem = shipments.find(item => item.id === detailId);
  function laborFee(item: Shipment, preview = false) {
    const config = item.reprice ? settings : item.pricingSnapshot || settings;
    if (!preview && item.laborFee !== undefined) return item.laborFee;
    if (!config) return item.laborFee ?? null;
    const cny = Number(item.cnyPrice);
    if (!Number.isFinite(cny) || cny <= 0) return null;
    const tier = [...config.tiers].reverse().find(t => cny >= t.from);
    return tier ? Math.round(tier.type === 'fixed' ? tier.value : cny * config.rate * tier.value / 100) : null;
  }
  const draftFee = laborFee(draft, true);
  // Tải danh sách nội bộ; bỏ qua phản hồi nếu đã rời trang.
  useEffect(() => {
    let active = true;
    api<{ items: Shipment[] }>("shipments/")
      .then((data) => {
        if (active) setShipments(data.items);
      })
      .catch((e) => {
        if (active)
          setError(e instanceof Error ? e.message : "Không thể tải đơn hàng.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  // Ngăn gửi nhiều thao tác cùng lúc và gom xử lý lỗi API.
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể kết nối máy chủ.");
    } finally {
      setBusy(false);
    }
  }
  // Sao chép đơn vào bản nháp để chỉnh sửa trước khi lưu.
  function editShipment(item: Shipment) {
    setDraft({ ...item });
    setEditing(true);
    setError("");
    setNotice("");
  }
  function manage() {
    setEditing(false);
    setError("");
  }
  function exportOrders(backup: boolean) {
    void run(async () => {
      const params = backup ? new URLSearchParams({ backup: '1' }) : new URLSearchParams({ year: filterYear, month: filterMonth, q: manageQuery.trim() });
      await downloadOrderFile(`shipments/export/?${params.toString()}`);
      setNotice(backup ? 'Đã tạo file sao lưu Excel toàn bộ đơn hàng.' : 'Đã tạo file Excel theo bộ lọc hiện tại.');
    });
  }
  // PATCH chỉ cập nhật trạng thái hoặc thanh toán, rồi đồng bộ đơn đã lưu.
  function quickUpdate(item: Shipment, changes: Partial<Shipment>) {
    void run(async () => {
      const saved = await api<Shipment>(`shipments/${item.id}/`, 'PATCH', changes);
      setShipments(list => list.map(row => row.id === saved.id ? saved : row));
      onChange(saved);
      setNotice(`Đã cập nhật đơn ${saved.code}.`);
    });
  }
  // Kiểm tra mã trùng; dùng POST để thêm và PUT để sửa đơn đã có.
  function saveShipment(e: FormEvent) {
    e.preventDefault();
    const normalized = normalizeCode(draft.code);
    if (!normalized || !draft.name.trim()) {
      setError("Vui lòng nhập mã đơn hàng và tên hàng.");
      return;
    }
    if (
      shipments.some(
        (item) =>
          item.id !== draft.id && normalizeCode(item.code) === normalized,
      )
    ) {
      setError("Mã đơn hàng này đã tồn tại. Hãy chỉnh sửa bản ghi hiện có.");
      return;
    }
    void run(async () => {
      const item = await api<Shipment>(
        draft.id ? `shipments/${draft.id}/` : "shipments/",
        draft.id ? "PUT" : "POST",
        { ...draft, surcharge: draft.surcharge ?? 0, weightFee: draft.weightFee ?? 0, domesticFee: draft.domesticFee ?? 0, code: normalized, productUrl: extractProductUrl(draft.productUrl || '') },
      );
      setShipments((list) =>
        draft.id
          ? list.map((p) => (p.id === item.id ? item : p))
          : [item, ...list],
      );
      onChange(item);
      setEditing(false);
      setNotice("Đã lưu trạng thái hàng.");
    });
  }
  // Chỉ bỏ đơn khỏi danh sách sau khi người dùng xác nhận và API xóa thành công.
  function removeShipment(item: Shipment) {
    if (window.confirm(`Xóa bản ghi ${item.code}?`))
      void run(async () => {
        await api(`shipments/${item.id}/`, "DELETE");
        setShipments((list) => list.filter((p) => p.id !== item.id));
        onChange(item, true);
        setNotice("Đã xóa bản ghi.");
      });
  }
  const monthFormatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
  });
  // Lấy tháng theo giờ Việt Nam; đơn cũ thiếu ngày tạo dùng ngày cập nhật.
  function orderMonth(item: Shipment) {
    const date = new Date(item.createdAt || item.updatedAt);
    return Number.isNaN(date.getTime())
      ? "unknown"
      : monthFormatter.format(date);
  }
  const availableYears = [
    ...new Set(
      shipments
        .map(orderMonth)
        .filter((month) => month !== "unknown")
        .map((month) => month.slice(0, 4)),
    ),
  ].sort((a, b) => b.localeCompare(a));
  // Kết hợp bộ lọc tháng/năm với từ khóa tìm người mua, mã hoặc tên hàng.
  const filtered = shipments.filter((item) => {
    const month = orderMonth(item);
    return (
      (!filterYear || month.slice(0, 4) === filterYear) &&
      (!filterMonth || month.slice(5) === filterMonth) &&
      `${item.buyerName || ""} ${item.code} ${item.trackingCode} ${item.name}`
        .toLocaleLowerCase("vi")
        .includes(manageQuery.trim().toLocaleLowerCase("vi"))
    );
  });
  // Gom đơn theo tháng và hiển thị tháng mới nhất trước.
  const groups = new Map<string, Shipment[]>();
  for (const item of filtered) {
    const key = orderMonth(item);
    groups.set(key, [...(groups.get(key) || []), item]);
  }
  const months = [...groups.entries()].sort(([a], [b]) => b.localeCompare(a));
  const totals = filtered.reduce((sum, item) => {
    const fee = laborFee(item);
    if (fee === null) sum.missing += 1;
    else sum.net += fee - (item.sharedFee ?? 0);
    return sum;
  }, { net: 0, missing: 0 });
  return (
    <section className="tool-card order-management">
      <div className="card-heading">
        <div>
          <span className="eyebrow">KHU VỰC NỘI BỘ</span>
          <h2>Quản lý đơn & mã vận đơn</h2>
        </div>
      </div>
      <p className="muted">
        Admin và nhân viên có thể thêm, sửa, xóa đơn và cập nhật trạng thái
        hàng. Danh sách được chia theo tháng tạo đơn (giờ Việt Nam), tháng mới
        nhất hiển thị trước.
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {(loading || busy) && (
        <p role="status">
          {loading ? "Đang tải đơn hàng..." : "Đang xử lý..."}
        </p>
      )}
      <fieldset className="form-lock" disabled={loading || busy}>
        {editing ? (
          <>
            <h3>{draft.id ? "Cập nhật đơn hàng" : "Thêm đơn hàng"}</h3>
            <form className="edit-form order-edit-form" onSubmit={saveShipment}>
              <label>
                Mã đơn hàng
                <input
                  required
                  maxLength={100}
                  value={draft.code}
                  onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                />
              </label>
              <label>
                Mã vận đơn Trung
                <input
                  maxLength={100}
                  placeholder="Có thể bổ sung khi có mã vận đơn Trung"
                  value={draft.trackingCode}
                  onChange={(e) =>
                    setDraft({ ...draft, trackingCode: e.target.value })
                  }
                />
              </label>
              <label>
                Tên người mua hàng
                <input
                  maxLength={150}
                  value={draft.buyerName || ""}
                  onChange={(e) =>
                    setDraft({ ...draft, buyerName: e.target.value })
                  }
                />
              </label>
              <label>
                Tên hàng / nội dung đơn
                <input
                  required
                  maxLength={200}
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </label>
              <label>
                Giá tệ (CNY)
                <input type="number" min="0" max="9999999999.99" step="0.01" value={draft.cnyPrice ?? ''} onChange={e => setDraft({ ...draft, cnyPrice: e.target.value })} />
              </label>
              <label>
                Tiền công (VNĐ)
                <input readOnly value={draftFee === null ? 'Chưa có giá tệ' : money(draftFee)} />
              </label>
              <label>
                Tỷ giá {draft.id ? 'đã chốt' : 'sẽ chốt'} (VNĐ / CNY)
                <input readOnly value={money((draft.reprice ? settings?.rate : draft.pricingSnapshot?.rate) ?? settings?.rate ?? 0)} />
              </label>
              {draft.id && <label className="order-reprice">
                <input type="checkbox" checked={draft.reprice ?? false} onChange={e => setDraft({ ...draft, reprice: e.target.checked })} />
                Áp dụng bảng giá hiện tại cho đơn này khi lưu
              </label>}
              <label>
                Phần công chia (VNĐ)
                <input type="number" required min="0" max="999999999999" step="1" value={draft.sharedFee ?? 0} onChange={e => setDraft({ ...draft, sharedFee: Number(e.target.value) })} />
              </label>
              <label>
                Phí cân khi hàng về (VNĐ)
                <input type="number" min="0" max="999999999999" step="1" placeholder="0" value={draft.weightFee ?? ''} onChange={e => setDraft({ ...draft, weightFee: e.target.value === '' ? undefined : Number(e.target.value) })} />
              </label>
              <label>
                Phí nội địa (VNĐ)
                <input type="number" min="0" max="999999999999" step="1" placeholder="0" value={draft.domesticFee ?? ''} onChange={e => setDraft({ ...draft, domesticFee: e.target.value === '' ? undefined : Number(e.target.value) })} />
              </label>
              <label>
                Phí khác / chưa phân loại (VNĐ)
                <input type="number" min="0" max="999999999999" step="1" placeholder="0" value={draft.surcharge ?? ''} onChange={e => setDraft({ ...draft, surcharge: e.target.value === '' ? undefined : Number(e.target.value) })} />
                <small>Các khoản nhập tại đây cộng với phụ phí ghi thêm trong sổ thanh toán. Phụ phí cũ chưa phân loại được giữ ở phí khác.</small>
              </label>
              <label>
                Nội dung phụ phí
                <input maxLength={500} placeholder="Phí vận chuyển, đóng gói..." value={draft.surchargeNote ?? ''} onChange={e => setDraft({ ...draft, surchargeNote: e.target.value })} />
              </label>
              <label>
                Phần thực nhận (VNĐ)
                <input readOnly value={draftFee === null ? 'Chưa có giá tệ' : money(draftFee - (draft.sharedFee ?? 0))} />
              </label>
              <label>
                Đường link sản phẩm
                <input type="url" maxLength={2000} placeholder="Dán link hoặc cả đoạn chia sẻ sản phẩm" value={draft.productUrl || ''}
                  onChange={e => setDraft({ ...draft, productUrl: e.target.value })}
                  onPaste={e => {
                    const text = e.clipboardData.getData('text');
                    const url = extractProductUrl(text);
                    if (/^https?:\/\//i.test(url)) { e.preventDefault(); setDraft({ ...draft, productUrl: url }); }
                  }}
                  onBlur={e => setDraft({ ...draft, productUrl: extractProductUrl(e.target.value) })} />
              </label>
              <label>
                Trạng thái hiện tại
                <select
                  value={draft.status}
                  onChange={(e) =>
                    setDraft({ ...draft, status: Number(e.target.value) })
                  }
                >
                  {statuses.map((s, i) => (
                    <option value={i} key={s}>
                      {i + 1}. {s}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Trạng thái thanh toán
                <select
                  value={draft.paymentStatusOverride ?? '__auto__'}
                  onChange={(e) => {
                    setDraft({ ...draft, paymentStatusOverride: e.target.value === '__auto__' ? null : e.target.value as PaymentStatus });
                  }}
                >
                  <option value="__auto__">Tự động theo sổ</option>
                  {Object.entries(paymentStatuses).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              {draft.totalDue != null ? <label>
                Còn cần thanh toán (VNĐ)
                <input readOnly value={draft.remainingAmount == null ? 'Chưa xác định' : money(draft.remainingAmount)} />
                <small>Tự tính sau khi lưu theo giá đơn và các khoản đã ghi trong sổ thanh toán.</small>
              </label> : (draft.paymentStatus === 'deposit' || draft.paymentStatus === 'domestic_shipping') && (
                <label>
                  Số tiền còn lại (VNĐ)
                  <input
                    required
                    type="number"
                    min="1"
                    max="999999999999"
                    step="1"
                    value={draft.remainingAmount || ''}
                    disabled={(draft.paymentCount ?? 0) > 0}
                    onChange={(e) => setDraft({ ...draft, remainingAmount: Number(e.target.value) })}
                  />
                </label>
              )}
              <label>
                Ghi chú
                <textarea
                  maxLength={1000}
                  value={draft.note}
                  onChange={(e) => setDraft({ ...draft, note: e.target.value })}
                />
              </label>
              <button className="primary" type="submit">
                Lưu trạng thái <Check size={16} />
              </button>
              <button className="text-button" type="button" onClick={manage}>
                Quay lại danh sách
              </button>
            </form>
          </>
        ) : (
          <div className="manage">
            <div className="manage-actions">
              <input
                aria-label="Tìm bản ghi"
                placeholder="Tìm tên người mua, mã đơn hàng, mã vận đơn Trung..."
                value={manageQuery}
                onChange={(e) => setManageQuery(e.target.value)}
              />
              <button className="primary" onClick={() => editShipment(blank)}>
                <Plus size={15} />
                Thêm mã đơn
              </button>
            </div>
            <div
              className="order-filters"
              role="group"
              aria-label="Lọc đơn theo thời gian"
            >
              <label>
                Tháng
                <select
                  value={filterMonth}
                  onChange={(e) => setFilterMonth(e.target.value)}
                >
                  <option value="">Tất cả các tháng</option>
                  {Array.from({ length: 12 }, (_, index) => {
                    const month = String(index + 1).padStart(2, "0");
                    return (
                      <option key={month} value={month}>
                        Tháng {index + 1}
                      </option>
                    );
                  })}
                </select>
              </label>
              <label>
                Năm
                <input
                  type="number"
                  min="1"
                  max="9999"
                  step="1"
                  list="order-years"
                  placeholder="Tất cả các năm"
                  value={filterYear}
                  onChange={(e) => setFilterYear(e.target.value)}
                />
                <datalist id="order-years">
                  {availableYears.map((year) => (
                    <option key={year} value={year} />
                  ))}
                </datalist>
              </label>
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  setFilterMonth("");
                  setFilterYear("");
                  setManageQuery("");
                }}
              >
                Xóa bộ lọc
              </button>
              <span className="filter-count" role="status">
                {filtered.length} đơn phù hợp
              </span>
            </div>
            <div className="order-export-actions" role="group" aria-label="Xuất và sao lưu đơn hàng">
              <button type="button" className="secondary" onClick={() => exportOrders(false)}><Download size={16} />Xuất Excel theo bộ lọc</button>
              <button type="button" className="secondary" onClick={() => exportOrders(true)}><Save size={16} />Sao lưu toàn bộ (.xlsx)</button>
              <small>Xuất theo tháng, năm và từ khóa đang chọn. Sao lưu toàn bộ gồm mọi đơn, thanh toán và lịch sử, không phụ thuộc bộ lọc.</small>
            </div>
            <p id="orders-scroll-help" className="orders-scroll-hint">↔ Vuốt hoặc kéo ngang để xem các cột. Mã đơn và tiêu đề cột được giữ cố định khi cuộn bảng.</p>
            {months.map(([month, items]) => (
              <div className="monthly-orders" key={month}>
                <div className="orders-table-scroll" role="region" aria-label={month === 'unknown' ? 'Bảng đơn chưa có ngày tạo' : `Bảng đơn tháng ${month.slice(5)}/${month.slice(0, 4)}`} aria-describedby="orders-scroll-help" tabIndex={0}>
                  <table className="orders-table">
                    <caption>
                      {month === "unknown"
                        ? "Chưa có ngày tạo"
                        : `Tháng ${month.slice(5)}/${month.slice(0, 4)}`}{" "}
                      · {items.length} đơn
                    </caption>
                    <colgroup>
                      <col className="orders-col-code" />
                      <col className="orders-col-tracking" />
                      <col className="orders-col-product" />
                      <col className="orders-col-buyer" />
                      <col className="orders-col-status" />
                      <col className="orders-col-payment" />
                      <col className="orders-col-money" />
                      <col className="orders-col-money" />
                      <col className="orders-col-money" />
                      <col className="orders-col-actions" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th scope="col">Mã đơn hàng</th>
                        <th scope="col">Mã vận đơn Trung</th>
                        <th scope="col">Tên hàng</th>
                        <th scope="col">Tên người mua hàng</th>
                        <th scope="col">Trạng thái</th>
                        <th scope="col">Thanh toán</th>
                        <th scope="col">Tiền công</th>
                        <th scope="col">Phần công chia</th>
                        <th scope="col">Phần thực nhận</th>
                        <th scope="col">Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.id}>
                          <td data-label="Mã đơn hàng">
                            <button type="button" className="text-button order-detail-link" aria-label={`Chi tiết ${item.code}`} onClick={() => setDetailId(item.id)}><strong>{item.code}</strong><span>Xem chi tiết</span></button>
                          </td>
                          <td data-label="Mã vận đơn Trung">{item.trackingCode || "Chưa có"}</td>
                          <td data-label="Tên hàng">
                            <div className="order-product">
                              <span>{item.name}</span>
                              <span className="order-price">Giá tệ: {item.cnyPrice != null && item.cnyPrice !== '' ? `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(Number(item.cnyPrice))} CNY` : 'Chưa có'}</span>
                              <span className="order-price">Tỷ giá chốt: {item.lockedRate != null ? money(item.lockedRate) : 'Chưa có'}/CNY</span>
                              <span className="order-price">Phụ phí: {money(item.surchargeTotal ?? item.surcharge ?? 0)}{item.surchargeNote ? ` · ${item.surchargeNote}` : ''}</span>
                              {item.productUrl ? <a href={item.productUrl} target="_blank" rel="noopener noreferrer">Mở link sản phẩm</a> : <span>Chưa có link</span>}
                            </div>
                          </td>
                          <td data-label="Tên người mua hàng">{item.buyerName || "Chưa có"}</td>
                          <td data-label="Trạng thái">
                            <select className="quick-status" aria-label={`Trạng thái ${item.code}`} value={item.status} onChange={e => quickUpdate(item, { status: Number(e.target.value) })}>
                              {statuses.map((status, index) => <option key={status} value={index}>{status}</option>)}
                            </select>
                          </td>
                          <td data-label="Thanh toán">
                            <div className="quick-payment">
                              <select aria-label={`Thanh toán ${item.code}`} value={item.paymentStatusOverride ?? '__auto__'} onChange={e => quickUpdate(item, { paymentStatusOverride: e.target.value === '__auto__' ? null : e.target.value as PaymentStatus })}>
                                <option value="__auto__">Tự động theo sổ</option>
                                {Object.entries(paymentStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                              </select>
                              <span>{paymentStatuses[item.paymentStatus || '']}</span>
                              <span>Tổng tiền: {item.totalDue == null ? 'Chưa xác định' : money(item.totalDue)}</span>
                              <span>Đã thu: {money(item.paidAmount ?? 0)}</span>
                              <strong>Còn cần thanh toán: {item.balance == null ? 'Chưa xác định' : money(item.remainingAmount ?? Math.ceil(Math.max(0, item.balance) / 1000) * 1000)}</strong>
                              {(item.balance ?? 0) < 0 && <span>Thu dư: {money(-item.balance!)}</span>}
                            </div>
                            <button type="button" className="text-button" onClick={() => setPaymentId(item.id)}>Sổ thanh toán</button>
                          </td>
                          <td className="order-money" data-label="Tiền công">{laborFee(item) === null ? 'Chưa có giá tệ' : money(laborFee(item)!)}</td>
                          <td className="order-money" data-label="Phần công chia">{money(item.sharedFee ?? 0)}</td>
                          <td className="order-money order-net" data-label="Phần thực nhận">{laborFee(item) === null ? 'Chưa có giá tệ' : money(laborFee(item)! - (item.sharedFee ?? 0))}</td>
                          <td data-label="Thao tác">
                            <div className="order-row-actions order-main-actions">
                              <button className="icon-button" aria-label={`Lịch sử ${item.code}`} onClick={() => setHistoryId(historyId === item.id ? null : item.id)}><History size={17} /></button>
                              <button
                                className="secondary order-edit-button"
                                aria-label={`Sửa ${item.code}`}
                                onClick={() => editShipment(item)}
                              >
                                <Pencil size={17} /> Chỉnh sửa đơn
                              </button>
                              <button
                                className="icon-button danger"
                                aria-label={`Xóa ${item.code}`}
                                onClick={() => removeShipment(item)}
                              >
                                <Trash2 size={17} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
            {!!shipments.length && !filtered.length && (
              <p className="inline-empty">
                Không có đơn hàng phù hợp với bộ lọc và từ khóa.
              </p>
            )}
            {!shipments.length && (
              <div className="inline-empty">
                Chưa có mã đơn nào. Thêm mã đơn và chọn trạng thái để bắt đầu
                tra cứu.
              </div>
            )}
            <div className="orders-total" role="status" aria-label="Tổng thực nhận theo bộ lọc">
              <div>
                <strong>Tổng thực nhận</strong>
                <span>{filtered.length} đơn theo bộ lọc hiện tại</span>
                {totals.missing > 0 && <small>Chưa tính {totals.missing} đơn chưa có giá tệ.</small>}
              </div>
              <b data-testid="orders-net-total">{money(totals.net)}</b>
            </div>
          </div>
        )}
      </fieldset>
      <Dialog open={!!historyItem} onOpenChange={open => { if (!open) setHistoryId(null); }}>
        <DialogContent className="lookup-modal order-history-modal">
          <DialogTitle>Lịch sử chỉnh sửa · {historyItem?.code}</DialogTitle>
          <DialogDescription>Các thay đổi được hiển thị từ mới nhất đến cũ nhất, theo giờ Việt Nam.</DialogDescription>
          {historyItem && <OrderHistory id={historyItem.id} code={historyItem.code} version={historyItem.updatedAt} />}
          <DialogClose asChild><button type="button" className="secondary">Đóng lịch sử</button></DialogClose>
        </DialogContent>
      </Dialog>
      <Dialog open={!!detailItem} onOpenChange={open => { if (!open) setDetailId(null); }}>
        <DialogContent className="lookup-modal order-details-modal">
          <DialogTitle>Chi tiết đơn · {detailItem?.code}</DialogTitle>
          <DialogDescription>Thông tin đơn, chi tiết phụ phí và số tiền còn cần thanh toán.</DialogDescription>
          {detailItem && <OrderDetails item={detailItem} />}
          <DialogClose asChild><button type="button" className="secondary">Đóng chi tiết</button></DialogClose>
        </DialogContent>
      </Dialog>
      <Dialog open={!!paymentItem} onOpenChange={open => { if (!open) setPaymentId(null); }}>
        <DialogContent className="lookup-modal">
          <DialogTitle>Sổ thanh toán · {paymentItem?.code}</DialogTitle>
          <DialogDescription>Ghi các khoản thu và hoàn tiền của đơn. Giao dịch đã ghi được giữ lại để đối soát.</DialogDescription>
          {paymentItem && <OrderPayments key={paymentItem.id} item={paymentItem} onSaved={saved => {
            setShipments(list => list.map(row => row.id === saved.id ? saved : row));
            onChange(saved);
          }} />}
        </DialogContent>
      </Dialog>
    </section>
  );
}
