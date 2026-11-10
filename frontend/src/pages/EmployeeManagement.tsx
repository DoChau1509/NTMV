import { FormEvent, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Account, api } from "../lib/order-api";

export default function EmployeeManagement() {
  const [employees, setEmployees] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // Tải danh sách nhân viên dành cho admin khi mở trang.
  useEffect(() => {
    let active = true;
    api<{ items: Account[] }>("employees/")
      .then((data) => {
        if (active) setEmployees(data.items);
      })
      .catch((e) => {
        if (active)
          setError(
            e instanceof Error
              ? e.message
              : "Không thể tải danh sách nhân viên.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  // Khóa biểu mẫu trong lúc gửi API và hiển thị kết quả thao tác.
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
  // Tạo nhân viên, thêm vào danh sách rồi làm trống biểu mẫu.
  function createEmployee(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    void run(async () => {
      const employee = await api<Account>("employees/", "POST", {
        username: data.get("username"),
        fullName: data.get("fullName"),
        password: data.get("password"),
      });
      setEmployees((list) => [...list, employee]);
      form.reset();
      setNotice("Đã tạo tài khoản nhân viên.");
    });
  }
  // Xác nhận trước khi xóa tài khoản; chỉ cập nhật danh sách khi API thành công.
  function removeEmployee(a: Account) {
    if (
      window.confirm(
        `Xóa tài khoản nhân viên ${a.username}? Tài khoản này sẽ không thể tiếp tục truy cập.`,
      )
    )
      void run(async () => {
        await api(`employees/${a.id}/`, "DELETE");
        setEmployees((list) => list.filter((i) => i.id !== a.id));
        setNotice("Đã xóa tài khoản nhân viên.");
      });
  }

  return (
    <section className="tool-card employee-management">
      <div className="card-heading">
        <div>
          <span className="eyebrow">KHU VỰC ADMIN</span>
          <h2>Quản lý nhân viên</h2>
        </div>
      </div>
      <p className="muted">
        Tạo và xóa tài khoản nhân viên. Nhân viên được quản lý đơn hàng, mã vận
        đơn, tỷ giá và tiền công.
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {(loading || busy) && (
        <p role="status">
          {loading ? "Đang tải danh sách nhân viên..." : "Đang xử lý..."}
        </p>
      )}
      <fieldset className="form-lock" disabled={loading || busy}>
        <div className="employee-workspace">
          <form className="edit-form employee-form" onSubmit={createEmployee}>
            <h3>Tạo tài khoản nhân viên</h3>
            <label>
              Họ và tên
              <input
                name="fullName"
                required
                maxLength={150}
                autoComplete="off"
              />
            </label>
            <label>
              Tên đăng nhập
              <input
                name="username"
                required
                maxLength={100}
                pattern="[a-zA-Z0-9_.@+\-]+"
                autoComplete="off"
              />
            </label>
            <label>
              Mật khẩu ban đầu
              <input
                name="password"
                type="password"
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
              />
            </label>
            <p className="fine-print">
              Tối thiểu 8 ký tự, tránh mật khẩu phổ biến hoặc chỉ gồm số.
            </p>
            <button className="primary" type="submit">
              <Plus size={15} />
              Tạo nhân viên
            </button>
          </form>
          <div className="employee-list">
            <h3>Danh sách nhân viên</h3>
            {employees.map((a) => (
              <article className="manage-row" key={a.id}>
                <div>
                  <strong>{a.fullName}</strong>
                  <p>{a.username} · Nhân viên</p>
                </div>
                <button
                  className="icon-button danger"
                  aria-label={`Xóa nhân viên ${a.username}`}
                  onClick={() => removeEmployee(a)}
                >
                  <Trash2 size={17} />
                </button>
              </article>
            ))}
            {!employees.length && (
              <p className="inline-empty">Chưa có tài khoản nhân viên.</p>
            )}
          </div>
        </div>
      </fieldset>
    </section>
  );
}
