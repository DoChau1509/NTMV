import { FormEvent, useEffect, useState } from "react";
import {
  Check,
  ClipboardList,
  Cloud,
  Package,
  Plus,
  Trash2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  defaultSettings,
  FeeTier,
  normalizeCode,
  Settings,
  Shipment,
  statuses,
  validSettings,
} from "./lib/shop";
import { Account, api } from "./lib/order-api";
import { HashRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import PriceLookup from "./pages/PriceLookup";
import ShipmentLookup from "./pages/ShipmentLookup";
import OrderManagement from "./pages/OrderManagement";
import EmployeeManagement from "./pages/EmployeeManagement";
import ProductManagement from "./pages/ProductManagement";
import CustomerGuide from "./pages/CustomerGuide";
import "./App.css";
import "./lookup-pages.css";
import "./responsive.css";
export default function App() {
  return (
    <HashRouter>
      <LookupApp />
    </HashRouter>
  );
}
function LookupApp() {
  const [settings, setSettings] = useState(defaultSettings);
  const [user, setUser] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [lookupItems, setLookupItems] = useState<Shipment[]>([]);
  const [selectedLookup, setSelectedLookup] = useState("");
  const [lookupError, setLookupError] = useState("");
  const [code, setCode] = useState("");
  const [searchedCode, setSearchedCode] = useState<string | null>(null);
  const [panel, setPanel] = useState<"settings" | "login" | null>(null);
  const [draftSettings, setDraftSettings] = useState<Settings>(settings);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canManage = user?.role === "admin" || user?.role === "employee";
  // Ưu tiên đơn được chọn khi một mã vận đơn khớp nhiều đơn hàng.
  const found =
    lookupItems.find((p) => p.id === selectedLookup) || lookupItems[0];
  // Tải phiên đăng nhập và tỷ giá; bỏ qua phản hồi khi trang đã đóng.
  useEffect(() => {
    let active = true;
    Promise.all([
      api<{ user: Account | null }>("session/"),
      api<Settings>("pricing/"),
    ])
      .then(([session, pricing]) => {
        if (active) {
          setUser(session.user);
          setSettings(pricing);
          setReady(true);
        }
      })
      .catch((e) => {
        if (active) setConnectionError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  function open(next: typeof panel) {
    setError("");
    setNotice("");
    setPanel(next);
  }
  // Khóa thao tác khi đang gửi API và hiển thị lỗi tại một nơi chung.
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể kết nối máy chủ.");
    } finally {
      setBusy(false);
    }
  }
  // Kiểm tra bản nháp trước khi lưu tỷ giá và thang tiền công lên máy chủ.
  function saveSettings(e: FormEvent) {
    e.preventDefault();
    if (!validSettings(draftSettings)) {
      setError(
        "Tỷ giá phải lớn hơn 0. Bậc đầu bắt đầu từ 0; các bậc tiếp theo phải tăng dần, không trùng nhau. Tiền công không âm; phần trăm tối đa 100%.",
      );
      return;
    }
    void run(async () => {
      setSettings(await api<Settings>("pricing/", "PUT", draftSettings));
      setPanel(null);
      setNotice("Đã cập nhật tỷ giá và thang tiền công.");
    });
  }
  // Chỉ sửa bậc công trong bản nháp; cấu hình thật đổi sau khi lưu.
  function updateTier(index: number, patch: Partial<FeeTier>) {
    setDraftSettings((s) => ({
      ...s,
      tiers: s.tiers.map((t, i) => (i === index ? { ...t, ...patch } : t)),
    }));
  }
  // Chuẩn hóa mã, xóa kết quả cũ rồi tra cứu đơn hàng qua API.
  async function search(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setLookupError("");
    setLookupItems([]);
    setSearchedCode(normalizeCode(code));
    try {
      const data = await api<{ items: Shipment[] }>(
        `lookup/?code=${encodeURIComponent(normalizeCode(code))}`,
      );
      setLookupItems(data.items);
      setSelectedLookup(data.items[0]?.id || "");
    } catch (e) {
      setLookupError(e instanceof Error ? e.message : "Không thể tra cứu.");
    } finally {
      setBusy(false);
    }
  }
  // Gửi thông tin đăng nhập và cập nhật tài khoản đang dùng trên giao diện.
  function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    void run(async () => {
      const session = await api<{ user: Account }>("login/", "POST", {
        username: data.get("username"),
        password: data.get("password"),
      });
      setUser(session.user);
      setPanel(null);
      setNotice("Đăng nhập thành công.");
    });
  }
  // Hủy phiên trên máy chủ trước khi xóa tài khoản khỏi giao diện.
  function logout() {
    void run(async () => {
      await api("logout/", "POST");
      setUser(null);
      setPanel(null);
      setNotice("Đã đăng xuất.");
    });
  }
  return (
    <div className="lookup-app">
      <div className="top-strip">
        <span>Tra giá rõ ràng · Theo dõi hàng dễ dàng</span>
        <span>CNY → VND</span>
      </div>
      <header className="lookup-header">
        <NavLink to="/huong-dan" className="brand">
          <span className="brand-mark">
            <Cloud size={25} />
          </span>
          <span className="brand-name">Ngạn Tâm Mạc Vấn<small>ĐẶT HÀNG & VẬN CHUYỂN</small></span>
        </NavLink>
        <nav aria-label="Điều hướng chính">
          <NavLink to="/huong-dan">Hướng dẫn</NavLink>
          <NavLink to="/tra-gia">Tra giá</NavLink>
          <NavLink to="/kiem-tra-hang">Kiểm tra hàng</NavLink>
        </nav>
        <div className="account-actions">
          {user ? (
            <>
              <span className="account-label">
                {user.fullName}
                <small>{user.role === "admin" ? "Admin" : "Nhân viên"}</small>
              </span>
              <>
                {canManage && (
                  <NavLink className="secondary" to="/quan-ly-san-pham">
                    <Package size={16} />
                    <span>Quản lý sản phẩm</span>
                  </NavLink>
                )}
                {canManage && (
                  <NavLink className="secondary" to="/quan-ly-don">
                    <ClipboardList size={16} />
                    <span>Quản lý đơn</span>
                  </NavLink>
                )}
              </>
              {user.role === "admin" && (
                <NavLink className="secondary" to="/nhan-vien">
                  Nhân viên
                </NavLink>
              )}
              <button className="text-button" disabled={busy} onClick={logout}>
                Đăng xuất
              </button>
            </>
          ) : (
            <button
              className="secondary"
              disabled={!ready || busy}
              onClick={() => open("login")}
            >
              Đăng nhập
            </button>
          )}
        </div>
      </header>
      <main className="lookup-main">
        {error && !panel && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        {connectionError && (
          <div className="form-error" role="alert">
            {connectionError}{" "}
            <button
              className="text-button"
              onClick={() => window.location.reload()}
            >
              Kết nối lại
            </button>
          </div>
        )}
        {!ready && !connectionError && (
          <p role="status" className="fine-print">
            Đang tải dữ liệu máy chủ...
          </p>
        )}
        <section className="intro">
          <div className="eyebrow">
            <span /> CÙNG BẠN TRÊN TỪNG CHẶNG HÀNG
          </div>
          <h1>
            Biết giá trước.
            <br />
            An tâm <em>đợi hàng về.</em>
          </h1>
          <p>
            Quy đổi giá Nhân dân tệ, tính sẵn tiền công và tra cứu
            <br className="desktop-break" /> trạng thái hàng của bạn trong một
            nơi.
          </p>
          <div className="intro-art" aria-hidden="true">
            <div className="route-line" />
            <span className="route-origin">TRUNG QUỐC</span>
            <div className="parcel">
              <Package size={72} strokeWidth={1} />
            </div>
            <span className="route-end">
              VIỆT NAM <Check size={14} />
            </span>
          </div>
        </section>
        <div className="tools-grid single-tool">
          {/* Chờ tải phiên rồi mới cho phép truy cập trang theo vai trò. */}
          <Routes>
            <Route path="/" element={<Navigate to="/huong-dan" replace />} />
            <Route path="/huong-dan" element={<CustomerGuide settings={settings} ready={ready} />} />
            <Route
              path="/tra-gia"
              element={
                <PriceLookup
                  isAdmin={user?.role === "admin"}
                  settings={settings}
                  ready={ready}
                  busy={busy}
                  canEdit={canManage}
                  onEdit={() => {
                    setDraftSettings(structuredClone(settings));
                    open("settings");
                  }}
                />
              }
            />
            <Route
              path="/kiem-tra-hang"
              element={
                <ShipmentLookup
                  code={code}
                  setCode={setCode}
                  search={search}
                  busy={busy}
                  ready={ready}
                  lookupError={lookupError}
                  searchedCode={searchedCode}
                  found={found}
                  lookupItems={lookupItems}
                  selectedLookup={selectedLookup}
                  setSelectedLookup={setSelectedLookup}
                  searching={busy && searchedCode !== null && panel === null}
                />
              }
            />
            <Route
              path="/quan-ly-don"
              element={
                !ready ? (
                  <p role="status">Đang kiểm tra quyền truy cập...</p>
                ) : canManage ? (
                  <OrderManagement
                    settings={settings}
                    key={user!.id}
                    onChange={(item, removed) =>
                      setLookupItems((list) =>
                        removed
                          ? list.filter((p) => p.id !== item.id)
                          : list.map((p) => (p.id === item.id ? item : p)),
                      )
                    }
                  />
                ) : (
                  <Navigate to="/tra-gia" replace />
                )
              }
            />
            <Route
              path="/quan-ly-san-pham"
              element={
                !ready ? (
                  <p role="status">Đang kiểm tra quyền truy cập...</p>
                ) : canManage ? (
                  <ProductManagement key={user!.id} />
                ) : (
                  <Navigate to="/huong-dan" replace />
                )
              }
            />
            <Route
              path="/nhan-vien"
              element={
                !ready ? (
                  <p role="status">Đang kiểm tra quyền truy cập...</p>
                ) : user?.role === "admin" ? (
                  <EmployeeManagement key={user.id} />
                ) : (
                  <Navigate to="/tra-gia" replace />
                )
              }
            />
            <Route path="*" element={<Navigate to="/huong-dan" replace />} />
          </Routes>
        </div>
        <section className="journey">
          <div className="section-title">
            <span className="eyebrow">TỪ LÚC MUA ĐẾN KHI NHẬN</span>
            <h2>6 chặng, luôn nắm rõ.</h2>
          </div>
          <div className="journey-steps">
            {statuses.map((s, i) => (
              <div key={s}>
                <span>0{i + 1}</span>
                <b>{s}</b>
              </div>
            ))}
          </div>
        </section>
        {/* <div className="local-note">
          <ShieldIcon />
          <p>
            Dữ liệu được nhân viên cập nhật và lưu trên máy chủ để tra cứu từ
            nhiều thiết bị. Trạng thái chưa tự đồng bộ với đơn vị vận chuyển.
          </p>
        </div> */}
      </main>
      <footer className="lookup-footer">
        <NavLink to="/huong-dan" className="brand">
          <span className="brand-name">Ngạn Tâm Mạc Vấn<small>ĐẶT HÀNG & VẬN CHUYỂN</small></span>
        </NavLink>
        <span>Giá rõ ràng. Hành trình minh bạch.</span>
        <small>Tra giá & Theo dõi hàng</small>
      </footer>
      {notice && (
        <div className="notification" role="status">
          <Check size={16} />
          {notice}
          <button aria-label="Đóng thông báo" onClick={() => setNotice("")}>
            ×
          </button>
        </div>
      )}
      <Dialog
        open={panel !== null}
        onOpenChange={(v) => {
          if (!v) setPanel(null);
        }}
      >
        <DialogContent className="lookup-modal">
          <DialogTitle>
            {panel === "login"
              ? "Đăng nhập quản lý"
              : "Tỷ giá & thang tiền công"}
          </DialogTitle>
          <DialogDescription>
            {panel === "settings"
              ? "Các thay đổi chỉ áp dụng sau khi lưu. Tiền công được cộng trực tiếp vào báo giá."
              : panel === "login"
                ? "Đăng nhập bằng tài khoản admin hoặc nhân viên được cấp."
                : "Admin và nhân viên đều được quản lý đơn hàng, mã vận đơn và trạng thái."}
          </DialogDescription>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {busy && (
            <p role="status" className="fine-print">
              Đang xử lý...
            </p>
          )}
          <fieldset className="form-lock" disabled={busy}>
            {panel === "login" && (
              <form className="edit-form" onSubmit={login}>
                <label>
                  Tên đăng nhập
                  <input
                    name="username"
                    autoComplete="username"
                    required
                    maxLength={100}
                  />
                </label>
                <label>
                  Mật khẩu
                  <input
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    required
                    maxLength={128}
                  />
                </label>
                <button type="submit" className="primary">
                  Đăng nhập
                </button>
                <p className="fine-print">
                  Liên hệ admin để được cấp tài khoản nhân viên.
                </p>
              </form>
            )}
            {panel === "settings" && user && (
              <form className="edit-form" onSubmit={saveSettings}>
                <label>
                  Tỷ giá VND cho 1 CNY
                  <input
                    required
                    type="number"
                    min="0.01"
                    max="1000000"
                    step="any"
                    value={
                      Number.isNaN(draftSettings.rate) ? "" : draftSettings.rate
                    }
                    onChange={(e) =>
                      setDraftSettings((s) => ({
                        ...s,
                        rate:
                          e.target.value === "" ? NaN : Number(e.target.value),
                      }))
                    }
                  />
                </label>
                <div className="subheading">
                  <h3>Thang tiền công</h3>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() =>
                      setDraftSettings((s) => ({
                        ...s,
                        tiers: [
                          ...s.tiers,
                          {
                            from: s.tiers[s.tiers.length - 1].from + 100,
                            value: 0,
                            type: "fixed",
                          },
                        ],
                      }))
                    }
                  >
                    <Plus size={14} />
                    Thêm bậc
                  </button>
                </div>
                <p className="fine-print">
                  Mỗi bậc tính từ số tệ bắt đầu đến dưới bậc kế tiếp. Bậc cuối
                  không có giới hạn trên. Công cố định tính bằng VND; công %
                  tính trên tiền hàng đã quy đổi.
                </p>
                <div className="fee-editor">
                  {draftSettings.tiers.map((t, i) => (
                    <div className="fee-row" key={i}>
                      <label>
                        Từ (CNY)
                        <input
                          aria-label={`Bậc ${i + 1} từ CNY`}
                          type="number"
                          required
                          min="0"
                          max="1000000000"
                          step="any"
                          disabled={i === 0}
                          value={Number.isNaN(t.from) ? "" : t.from}
                          onChange={(e) =>
                            updateTier(i, {
                              from:
                                e.target.value === ""
                                  ? NaN
                                  : Number(e.target.value),
                            })
                          }
                        />
                      </label>
                      <label>
                        Loại công
                        <select
                          aria-label={`Loại công bậc ${i + 1}`}
                          value={t.type}
                          onChange={(e) =>
                            updateTier(i, {
                              type: e.target.value as FeeTier["type"],
                            })
                          }
                        >
                          <option value="fixed">Cố định (VND)</option>
                          <option value="percent">Phần trăm (%)</option>
                        </select>
                      </label>
                      <label>
                        Mức công
                        <input
                          aria-label={`Mức công bậc ${i + 1}`}
                          type="number"
                          min="0"
                          max={t.type === "percent" ? 100 : 1e9}
                          step="any"
                          required
                          value={Number.isNaN(t.value) ? "" : t.value}
                          onChange={(e) =>
                            updateTier(i, {
                              value:
                                e.target.value === ""
                                  ? NaN
                                  : Number(e.target.value),
                            })
                          }
                        />
                      </label>
                      <button
                        className="icon-button danger"
                        aria-label={`Xóa bậc ${i + 1}`}
                        type="button"
                        disabled={i === 0}
                        onClick={() =>
                          setDraftSettings((s) => ({
                            ...s,
                            tiers: s.tiers.filter((_, n) => n !== i),
                          }))
                        }
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
                <button className="primary" type="submit">
                  Lưu cấu hình <Check size={16} />
                </button>
                <button
                  className="text-button"
                  type="button"
                  onClick={() =>
                    setDraftSettings(structuredClone(defaultSettings))
                  }
                >
                  Dùng lại cấu hình mẫu
                </button>
              </form>
            )}
          </fieldset>
        </DialogContent>
      </Dialog>
    </div>
  );
}
