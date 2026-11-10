import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/order-api";

export default function OrderContact({ isAdmin }: { isAdmin: boolean }) {
  const [url, setUrl] = useState("");
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // Đọc liên kết liên hệ hiện tại cho khách và admin.
  useEffect(() => {
    let active = true;
    api<{ url: string }>("contact/")
      .then((data) => {
        if (active) {
          setUrl(data.url || "");
          setDraft(data.url || "");
        }
      })
      .catch((e) => {
        if (active)
          setError(
            e instanceof Error ? e.message : "Không thể tải liên kết đặt hàng.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  // Admin lưu liên kết mới; chuỗi rỗng dùng để gỡ liên kết.
  async function save(event: FormEvent) {
    event.preventDefault();
    if (saving || !isAdmin) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const data = await api<{ url: string }>("contact/", "PUT", {
        url: draft.trim(),
      });
      setUrl(data.url);
      setEditing(false);
      setNotice("Đã cập nhật liên kết đặt hàng.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể lưu liên kết.");
    } finally {
      setSaving(false);
    }
  }
  // Chỉ tạo liên kết có giao thức HTTP hoặc HTTPS.
  const safeUrl = /^https?:\/\//i.test(url) ? url : "";
  return (
    <aside className="order-contact" aria-label="Liên hệ đặt hàng">
      <h3>Đặt hàng cùng Ngạn Tâm Mạc Vấn</h3>
      {loading ? (
        <p role="status">Đang tải liên kết đặt hàng...</p>
      ) : safeUrl ? (
        <p>
          Bạn muốn tìm hiểu thêm?{" "}
          <a href={safeUrl} target="_blank" rel="noopener noreferrer">
            Nhắn tin qua trang cá nhân để được tư vấn
          </a>
          .
        </p>
      ) : (
        <p>Liên hệ nhân viên để được hỗ trợ đặt hàng.</p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {isAdmin &&
        (editing ? (
          <form className="edit-form" onSubmit={save}>
            <label>
              Liên kết trang cá nhân
              <input
                type="url"
                maxLength={500}
                placeholder="https://..."
                value={draft}
                disabled={saving}
                onChange={(e) => setDraft(e.target.value)}
              />
            </label>
            <p className="fine-print">Để trống để gỡ liên kết đặt hàng.</p>
            <button type="submit" className="primary" disabled={saving}>
              {saving ? "Đang lưu..." : "Lưu liên kết"}
            </button>
            <button
              type="button"
              className="text-button"
              disabled={saving}
              onClick={() => setEditing(false)}
            >
              Hủy
            </button>
          </form>
        ) : (
          <button
            type="button"
            className="text-button"
            disabled={loading}
            onClick={() => {
              setDraft(url);
              setError("");
              setNotice("");
              setEditing(true);
            }}
          >
            Chỉnh liên kết đặt hàng
          </button>
        ))}
    </aside>
  );
}
