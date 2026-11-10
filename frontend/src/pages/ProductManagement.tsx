import { FormEvent, useEffect, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, Folder, Package, Pencil, Plus, Trash2 } from 'lucide-react';
import { api } from '../lib/order-api';
import { money } from '../lib/shop';
import { CustomerOrder, Gathering, GatheringItem, deadlineWarning, displayDay, formatCny, itemStatuses, lineCents, lineVnd, orderCents, orderVnd, remainingVnd, vietnamDay } from '../lib/gatherings';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../components/ui/dialog';
import '../product-management.css';

type BatchDraft = { id?: string; name: string; startsOn: string; endsOn: string };
type OrderDraft = { id?: string; gatheringId: string; customerName: string; profileUrl: string; paidAmount: string; discountAmount: string; items: GatheringItem[] };
const newItem = (): GatheringItem => ({ name: '', note: '', quantity: 1, unitPrice: '', unitPriceVnd: null, depositDueOn: null, status: 'bought' });
const displayVndTotal = (value: bigint | null) => value === null ? 'Chưa đủ giá Việt' : value < 0n ? 'Giảm giá vượt tiền hàng' : money(value);
const batchesPerPage = 4;
const searchText = (value: string) => value.trim().toLocaleLowerCase('vi').normalize('NFD').replace(/\p{M}/gu, '').replace(/đ/g, 'd');

export default function ProductManagement() {
  const [batches, setBatches] = useState<Gathering[]>([]);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reload, setReload] = useState(0);
  const [now, setNow] = useState(() => new Date());
  const [batchDraft, setBatchDraft] = useState<BatchDraft | null>(null);
  const [orderDraft, setOrderDraft] = useState<OrderDraft | null>(null);
  const [batchQuery, setBatchQuery] = useState('');
  const [customerQuery, setCustomerQuery] = useState('');
  const [batchPage, setBatchPage] = useState(0);
  const customerTerm = searchText(customerQuery);
  const matchesCustomer = (order: CustomerOrder) => searchText(order.customerName).includes(customerTerm);
  const filteredBatches = batches.filter(batch => searchText(batch.name).includes(searchText(batchQuery)) && (!customerTerm || batch.orders.some(matchesCustomer)));
  const page = Math.min(batchPage, Math.max(0, Math.ceil(filteredBatches.length / batchesPerPage) - 1));
  const pageStart = page * batchesPerPage;
  const visibleBatches = filteredBatches.slice(pageStart, pageStart + batchesPerPage);
  const current = visibleBatches.find(batch => batch.id === selected) || visibleBatches[0];

  function updateSearch(value: string, field: 'batch' | 'customer') {
    if (field === 'batch') setBatchQuery(value);
    else setCustomerQuery(value);
    setBatchPage(0);
    setSelected('');
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError('');
    api<{ items: Gathering[] }>('gatherings/').then(data => {
      if (active) setBatches(data.items);
    }).catch(e => { if (active) setLoadError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);

  useEffect(() => {
    const update = () => setNow(new Date());
    const timer = window.setInterval(update, 60000);
    window.addEventListener('focus', update);
    return () => { window.clearInterval(timer); window.removeEventListener('focus', update); };
  }, []);

  async function run(action: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError(''); setNotice('');
    try { await action(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Không thể kết nối máy chủ.'); }
    finally { busyRef.current = false; setBusy(false); }
  }
  function openBatch(batch?: Gathering) {
    setError('');
    setBatchDraft(batch ? { id: batch.id, name: batch.name, startsOn: batch.startsOn, endsOn: batch.endsOn } : { name: '', startsOn: vietnamDay(), endsOn: vietnamDay() });
  }
  function openOrder(order?: CustomerOrder) {
    if (!current) return;
    setError('');
    setOrderDraft(order ? { ...order, paidAmount: String(order.paidAmount), discountAmount: order.discountAmount ? String(order.discountAmount) : '', items: order.items.map(item => ({ ...item })) } : {
      gatheringId: current.id, customerName: '', profileUrl: '', paidAmount: '0', discountAmount: '', items: [newItem()],
    });
  }
  function updateItem(index: number, patch: Partial<GatheringItem>) {
    setOrderDraft(draft => draft && ({ ...draft, items: draft.items.map((item, i) => i === index ? { ...item, ...patch } : item) }));
  }
  function saveBatch(e: FormEvent) {
    e.preventDefault();
    if (!batchDraft) return;
    if (batchDraft.endsOn < batchDraft.startsOn) { setError('Ngày kết thúc phải từ ngày bắt đầu trở đi.'); return; }
    const draft = batchDraft;
    void run(async () => {
      const saved = await api<Gathering>(draft.id ? `gatherings/${draft.id}/` : 'gatherings/', draft.id ? 'PUT' : 'POST', draft);
      setBatches(list => draft.id ? list.map(batch => batch.id === saved.id ? saved : batch) : [saved, ...list]);
      setBatchQuery(''); setCustomerQuery('');
      setBatchPage(draft.id ? Math.floor(Math.max(0, batches.findIndex(batch => batch.id === saved.id)) / batchesPerPage) : 0);
      setSelected(saved.id); setBatchDraft(null); setNotice('Đã lưu đợt gom.');
    });
  }
  function saveOrder(e: FormEvent) {
    e.preventDefault();
    if (!orderDraft) return;
    const draft = orderDraft;
    const discount = Number(draft.discountAmount);
    if (!Number.isSafeInteger(discount) || discount < 0 || discount > 1e12) { setError('Giảm giá phải là số nguyên VND từ 0 đến 1.000.000.000.000.'); return; }
    const subtotal = orderVnd(draft.items);
    if (subtotal !== null && BigInt(discount) > subtotal) { setError('Giảm giá không được vượt quá tổng tiền hàng VND.'); return; }
    void run(async () => {
      const saved = await api<CustomerOrder>(draft.id ? `gathering-orders/${draft.id}/` : `gatherings/${draft.gatheringId}/orders/`, draft.id ? 'PUT' : 'POST', {
        customerName: draft.customerName, profileUrl: draft.profileUrl, paidAmount: Number(draft.paidAmount),
        discountAmount: discount,
        items: draft.items.map(item => ({ id: item.id, name: item.name, note: item.note ?? '', quantity: item.quantity, unitPrice: item.unitPrice, unitPriceVnd: item.unitPriceVnd ?? null,
          depositDueOn: item.depositDueOn, status: item.status })),
      });
      setBatches(list => list.map(batch => batch.id === saved.gatheringId ? { ...batch, orders: draft.id ? batch.orders.map(order => order.id === saved.id ? saved : order) : [...batch.orders, saved] } : batch));
      setOrderDraft(null); setNotice('Đã lưu đơn khách và các mặt hàng.');
    });
  }
  function removeBatch(batch: Gathering) {
    if (!window.confirm(`Xóa đợt gom “${batch.name}”?`)) return;
    void run(async () => {
      await api(`gatherings/${batch.id}/`, 'DELETE');
      setBatches(list => list.filter(row => row.id !== batch.id)); setNotice('Đã xóa đợt gom.');
    });
  }
  function removeOrder(order: CustomerOrder) {
    if (!window.confirm(`Xóa đơn của ${order.customerName} và toàn bộ ${order.items.length} mặt hàng?`)) return;
    void run(async () => {
      await api(`gathering-orders/${order.id}/`, 'DELETE');
      setBatches(list => list.map(batch => batch.id === order.gatheringId ? { ...batch, orders: batch.orders.filter(row => row.id !== order.id) } : batch));
      setNotice('Đã xóa đơn khách.');
    });
  }

  const orders = current?.orders.filter(matchesCustomer) || [];
  const draftRemaining = orderDraft ? remainingVnd(orderDraft.items, Number(orderDraft.discountAmount), Number(orderDraft.paidAmount)) : null;
  return (
    <section className="tool-card product-management">
      <div className="product-toolbar">
        <div><span className="eyebrow">ADMIN & NHÂN VIÊN</span><h2>Quản lý sản phẩm</h2></div>
        <button className="primary" disabled={loading || !!loadError || busy} onClick={() => openBatch()}><Plus size={16} />Thêm đợt gom</button>
      </div>
      <p className="muted">Sắp xếp theo đợt gom, đơn khách và từng mặt hàng. Tiền còn lại được tính tự động theo tổng đơn VND và tiền khách đã thanh toán.</p>
      {loading && <p role="status">Đang tải các đợt gom...</p>}
      {loadError && <div className="form-error" role="alert">{loadError} <button className="text-button" onClick={() => setReload(value => value + 1)}>Thử lại</button></div>}
      {error && !batchDraft && !orderDraft && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="product-notice" role="status">{notice}</p>}
      {!loading && !loadError && <fieldset className="form-lock" disabled={busy}>
        <div className="product-search-filters" role="search" aria-label="Tìm đợt gom và khách hàng">
          <label className="product-search">Tìm kiếm đợt gom<input type="search" value={batchQuery} onChange={e => updateSearch(e.target.value, 'batch')} placeholder="Nhập tên đợt gom..." /></label>
          <label className="product-search">Tìm kiếm khách hàng<input type="search" value={customerQuery} onChange={e => updateSearch(e.target.value, 'customer')} placeholder="Nhập tên khách hàng..." /></label>
          {(batchQuery || customerQuery) && <button className="text-button" onClick={() => { setBatchQuery(''); setCustomerQuery(''); setBatchPage(0); setSelected(''); }}>Xóa tìm kiếm</button>}
          <p className="fine-print">Kết hợp hai ô để tìm khách trong một đợt gom. Tìm tên khách riêng để xem các đợt có khách đó; hỗ trợ nhập không dấu.</p>
        </div>
        <div className="product-workspace">
          <aside className="gathering-sidebar" aria-label="Các đợt gom">
            <h3>Đợt gom <span>({filteredBatches.length}{batchQuery || customerQuery ? ` / ${batches.length}` : ''})</span></h3>
            {!batches.length && <p className="fine-print">Chưa có đợt gom. Thêm đợt đầu tiên để bắt đầu.</p>}
            {batches.length > 0 && !filteredBatches.length && <p className="fine-print">Không có đợt gom phù hợp với tìm kiếm.</p>}
            {filteredBatches.length > 0 && <>
              <button className="secondary gathering-page-button" aria-label="Xem 4 đợt gom trước" disabled={busy || page === 0} onClick={() => { setBatchPage(page - 1); setSelected(''); }}><ChevronUp size={16} />Lên</button>
              <p className="gathering-page-count" role="status">Đang hiển thị {pageStart + 1}–{Math.min(pageStart + batchesPerPage, filteredBatches.length)} / {filteredBatches.length} đợt gom</p>
            </>}
            {visibleBatches.map(batch => {
              const alerts = batch.orders.filter(order => order.items.some(item => deadlineWarning(item, now, remainingVnd(order.items, order.discountAmount, order.paidAmount)))).length;
              return <button key={batch.id} className={`gathering-folder ${current?.id === batch.id ? 'selected' : ''}`} aria-pressed={current?.id === batch.id} onClick={() => setSelected(batch.id)}>
                <Folder size={20} /><span><strong>{batch.name}</strong><small>{displayDay(batch.startsOn)} – {displayDay(batch.endsOn)}</small><small>{customerTerm ? `${batch.orders.filter(matchesCustomer).length} / ` : ''}{batch.orders.length} đơn khách{alerts > 0 && ` · ${alerts} đơn cần thanh toán`}</small></span>
              </button>;
            })}
            {filteredBatches.length > 0 && <button className="secondary gathering-page-button" aria-label="Xem 4 đợt gom tiếp theo" disabled={busy || pageStart + batchesPerPage >= filteredBatches.length} onClick={() => { setBatchPage(page + 1); setSelected(''); }}><ChevronDown size={16} />Xuống</button>}
          </aside>
          <div className="gathering-content">
            {current ? <>
              <div className="product-toolbar">
                <div><h3>{current.name}</h3><p className="fine-print">Thời gian gom: {displayDay(current.startsOn)} – {displayDay(current.endsOn)}</p></div>
                <div className="product-actions">
                  <button className="secondary" onClick={() => openBatch(current)}><Pencil size={14} />Sửa đợt</button>
                  <button className="secondary danger" disabled={busy || current.orders.length > 0} title={current.orders.length ? 'Xóa các đơn khách trước khi xóa đợt gom' : undefined} onClick={() => removeBatch(current)}><Trash2 size={14} />Xóa đợt</button>
                  <button className="primary" onClick={() => openOrder()}><Plus size={14} />Thêm đơn khách</button>
                </div>
              </div>
              <div className="gathering-summary">
                <span>{current.orders.length} đơn khách</span>
                <span>{current.orders.reduce((sum, order) => sum + order.items.length, 0)} mặt hàng</span>
                <strong>Tổng đợt: {formatCny(current.orders.reduce((sum, order) => sum + orderCents(order.items), 0n))}</strong>
                <strong>Tổng tệ chưa mua: {formatCny(current.orders.reduce((sum, order) => sum + orderCents(order.items.filter(item => item.status === 'not_bought')), 0n))}</strong>
              </div>
              {customerTerm && <p className="fine-print" role="status">Tìm thấy {orders.length} đơn khách phù hợp trong đợt gom này.</p>}
              {!orders.length && <p className="inline-empty">{customerTerm ? 'Không tìm thấy đơn phù hợp.' : 'Đợt gom chưa có đơn khách.'}</p>}
              {orders.map(order => {
                const remaining = remainingVnd(order.items, order.discountAmount, order.paidAmount);
                const warnings = order.items.map(item => deadlineWarning(item, now, remaining)).filter(Boolean);
                return <article className="customer-order" key={order.id}>
                  <div className="product-toolbar">
                    <div><h4>{order.customerName}</h4>{order.profileUrl && <a href={order.profileUrl} target="_blank" rel="noopener noreferrer">Trang cá nhân ↗</a>}</div>
                    <div className="product-actions"><button className="secondary" onClick={() => openOrder(order)}><Pencil size={14} />Sửa đơn</button><button className="secondary danger" aria-label={`Xóa đơn của ${order.customerName}`} onClick={() => removeOrder(order)}><Trash2 size={14} /></button></div>
                  </div>
                  <div className="customer-order-money">
                    <span>Đã thanh toán: <b>{money(order.paidAmount)}</b></span>
                    <span>Tiền còn lại: <b>{displayVndTotal(remaining)}</b></span>
                    <span>Tổng tệ: <b>{formatCny(orderCents(order.items))}</b></span>
                    <span>Tiền hàng (VND): <b>{displayVndTotal(orderVnd(order.items))}</b></span>
                    <span>Giảm giá: <b>{money(order.discountAmount ?? 0)}</b></span>
                    <span>Tổng đơn sau giảm (VND): <b>{displayVndTotal(orderVnd(order.items, order.discountAmount))}</b></span>
                  </div>
                  {warnings.length > 0 && <div className="deposit-warnings" role="status" aria-label={`Nhắc thanh toán của ${order.customerName}`}><strong><AlertCircle size={16} />Nhắc thanh toán</strong>{warnings.map((warning, i) => <p key={i}>{warning}</p>)}</div>}
                  <details className="customer-products"><summary><Package size={15} />Xem {order.items.length} mặt hàng</summary>
                    <div className="product-table-scroll" tabIndex={0} role="region" aria-label={`Mặt hàng của ${order.customerName}`}><table className="product-table"><thead><tr><th>Mặt hàng</th><th>Số lượng</th><th>Giá tệ / món</th><th>Tổng tệ</th><th>Giá Việt / món</th><th>Tổng VND</th><th>Hạn thanh toán nốt</th><th>Tình trạng hàng</th></tr></thead><tbody>
                      {order.items.map(item => <tr key={item.id}><td>{item.name}{item.note && <div className="product-item-note"><strong>Ghi chú:</strong> {item.note}</div>}</td><td>{item.quantity}</td><td>{formatCny(lineCents({ ...item, quantity: 1 }))}</td><td>{formatCny(lineCents(item))}</td><td>{item.unitPriceVnd == null ? 'Chưa cập nhật' : money(item.unitPriceVnd)}</td><td>{lineVnd(item) === null ? 'Chưa cập nhật' : money(lineVnd(item)!)}</td><td>{item.depositDueOn ? displayDay(item.depositDueOn) : '—'}</td><td>{itemStatuses[item.status]}</td></tr>)}
                    </tbody></table></div>
                  </details>
                </article>;
              })}
            </> : <div className="inline-empty"><Folder size={32} /><p>{batches.length ? 'Không tìm thấy đợt gom hoặc khách hàng phù hợp. Hãy thử đổi từ khóa tìm kiếm.' : 'Các đơn khách sẽ nằm trong từng thư mục đợt gom.'}</p></div>}
          </div>
        </div>
      </fieldset>}
      <Dialog open={!!batchDraft} onOpenChange={open => { if (!open && !busy) { setBatchDraft(null); setError(''); } }}>
        <DialogContent className="lookup-modal"><DialogTitle>{batchDraft?.id ? 'Sửa đợt gom' : 'Thêm đợt gom'}</DialogTitle><DialogDescription>Đặt tên thư mục và khoảng thời gian nhận gom hàng.</DialogDescription>
          {error && <p className="form-error" role="alert">{error}</p>}
          {batchDraft && <form className="edit-form" onSubmit={saveBatch}><fieldset className="form-lock" disabled={busy}>
            <label>Tên đợt gom<input required maxLength={200} value={batchDraft.name} onChange={e => setBatchDraft({ ...batchDraft, name: e.target.value })} /></label>
            <label>Ngày bắt đầu<input required type="date" value={batchDraft.startsOn} onChange={e => setBatchDraft({ ...batchDraft, startsOn: e.target.value })} /></label>
            <label>Ngày kết thúc<input required type="date" min={batchDraft.startsOn} value={batchDraft.endsOn} onChange={e => setBatchDraft({ ...batchDraft, endsOn: e.target.value })} /></label>
            <button className="primary" type="submit">{busy ? 'Đang lưu...' : 'Lưu đợt gom'}</button>
          </fieldset></form>}
        </DialogContent>
      </Dialog>
      <Dialog open={!!orderDraft} onOpenChange={open => { if (!open && !busy) { setOrderDraft(null); setError(''); } }}>
        <DialogContent className="lookup-modal product-order-modal"><DialogTitle>{orderDraft?.id ? 'Sửa đơn khách' : 'Thêm đơn khách'}</DialogTitle><DialogDescription>Nhập giá Việt riêng cho từng món. Tổng đơn VND = tổng số lượng × giá Việt của các món − giảm giá đơn. Tiền còn lại tự tính sau khi trừ tiền đã thanh toán.</DialogDescription>
          {error && <p className="form-error" role="alert">{error}</p>}
          {orderDraft && <form className="edit-form" onSubmit={saveOrder}><fieldset className="form-lock" disabled={busy}>
            <div className="customer-fields">
              <label>Tên khách hàng<input required maxLength={150} value={orderDraft.customerName} onChange={e => setOrderDraft({ ...orderDraft, customerName: e.target.value })} /></label>
              <label>Link trang cá nhân<input type="url" maxLength={500} placeholder="https://..." value={orderDraft.profileUrl} onChange={e => setOrderDraft({ ...orderDraft, profileUrl: e.target.value })} /></label>
              <label>Đã thanh toán (VND)<input required type="number" min="0" max="1000000000000" step="1" value={orderDraft.paidAmount} onChange={e => setOrderDraft({ ...orderDraft, paidAmount: e.target.value })} /></label>
              <label>Tiền còn lại (VND)<input readOnly value={displayVndTotal(draftRemaining)} /></label>
              <label>Giảm giá đơn (VND)<input type="number" min="0" max="1000000000000" step="1" placeholder="Không giảm giá" value={orderDraft.discountAmount} onChange={e => setOrderDraft({ ...orderDraft, discountAmount: e.target.value })} /></label>
            </div>
            <p className="fine-print">Giảm giá để trống hoặc nhập 0 nếu không áp dụng. Tiền còn lại = tổng đơn sau giảm − đã thanh toán, tối thiểu 0 VND. Nhập đủ giá Việt để tính tiền còn lại.</p>
            <div className="product-toolbar"><h3>Các mặt hàng</h3><button type="button" className="secondary" disabled={busy || orderDraft.items.length >= 100} onClick={() => setOrderDraft({ ...orderDraft, items: [...orderDraft.items, newItem()] })}><Plus size={14} />Thêm mặt hàng</button></div>
            {orderDraft.items.map((item, index) => <div className="product-item-editor" key={index}>
              <div className="product-toolbar"><strong>Mặt hàng {index + 1}</strong><button type="button" className="text-button danger" disabled={busy || orderDraft.items.length === 1} aria-label={`Xóa mặt hàng ${index + 1}`} onClick={() => setOrderDraft({ ...orderDraft, items: orderDraft.items.filter((_, i) => i !== index) })}><Trash2 size={14} />Xóa</button></div>
              <div className="product-item-fields">
                <label className="product-name-field">Tên mặt hàng<input required maxLength={200} value={item.name} onChange={e => updateItem(index, { name: e.target.value })} /></label>
                <label className="product-note-field">Ghi chú sản phẩm<textarea rows={3} maxLength={2000} placeholder="Màu sắc, kích cỡ hoặc yêu cầu riêng..." value={item.note ?? ''} onChange={e => updateItem(index, { note: e.target.value })} /></label>
                <label>Số lượng<input required type="number" min="1" max="1000000" step="1" value={item.quantity || ''} onChange={e => updateItem(index, { quantity: Number(e.target.value) })} /></label>
                <label>Giá tệ / món (CNY)<input required type="number" min="0" max="9999999999.99" step="0.01" value={item.unitPrice} onChange={e => updateItem(index, { unitPrice: e.target.value })} /></label>
                <label>Giá Việt / món (VND)<input type="number" min="0" max="1000000000000" step="1" placeholder="Chưa cập nhật" value={item.unitPriceVnd ?? ''} onChange={e => updateItem(index, { unitPriceVnd: e.target.value === '' ? null : Number(e.target.value) })} /></label>
                <label>Tình trạng hàng<select value={item.status} onChange={e => updateItem(index, { status: e.target.value as GatheringItem['status'] })}>{Object.entries(itemStatuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
                <label>Hạn thanh toán nốt<input type="date" value={item.depositDueOn || ''} onChange={e => updateItem(index, { depositDueOn: e.target.value || null })} /></label>
              </div>
              <p className="product-line-total">Tổng mặt hàng: <b>{formatCny(lineCents(item))}</b> · VND: <b>{lineVnd(item) === null ? 'Chưa cập nhật' : money(lineVnd(item)!)}</b></p>
            </div>)}
            <div className="gathering-summary">
              <span>Tổng tệ: {formatCny(orderCents(orderDraft.items))}</span>
              <span>Tiền hàng (VND): {displayVndTotal(orderVnd(orderDraft.items))}</span>
              <span>Giảm giá: {money(Number(orderDraft.discountAmount) || 0)}</span>
              <strong>Tổng đơn sau giảm (VND): {displayVndTotal(orderVnd(orderDraft.items, Number(orderDraft.discountAmount)))}</strong>
              <span>Đã thanh toán: {money(Number(orderDraft.paidAmount) || 0)}</span>
              <span>Tiền còn lại: {displayVndTotal(draftRemaining)}</span>
            </div>
            <p className="fine-print">Có thể đặt hạn thanh toán cho từng món. Nhắc trước hạn 1 ngày, trong ngày đến hạn và khi quá hạn; tự ngừng nhắc khi đơn khách đã thanh toán đủ.</p>
            <button className="primary" type="submit">{busy ? 'Đang lưu...' : 'Lưu đơn khách'}</button>
          </fieldset></form>}
        </DialogContent>
      </Dialog>
    </section>
  );
}
