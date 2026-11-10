export type Account = { id: string; username: string; fullName: string; role: 'admin' | 'employee' };
let csrfToken = '';
export async function downloadOrderFile(path: string): Promise<void> {
 const response = await fetch(`/api/order/${path}`, { credentials: 'same-origin' });
 if (!response.ok) {
  const data = await response.json().catch(() => ({}));
  throw new Error(data.error || 'Không thể tải file Excel. Vui lòng thử lại.');
 }
 if (!response.headers.get('Content-Type')?.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')) {
  throw new Error('Máy chủ không trả về file Excel hợp lệ.');
 }
 const blob = await response.blob();
 const url = URL.createObjectURL(blob);
 const link = document.createElement('a');
 link.href = url;
 link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || 'don-hang.xlsx';
 document.body.appendChild(link);
 try { link.click(); }
 finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
}
// Gửi cookie phiên và kèm CSRF cho yêu cầu ghi dữ liệu.
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
 const response = await fetch(`/api/order/${path}`, { method, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(method !== 'GET' ? { 'X-CSRFToken': csrfToken } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
 let data;
 try { data = await response.json(); } catch { throw new Error('Không kết nối được API. Kiểm tra backend và cấu hình proxy.'); }
 if (!response.ok) throw new Error(data.error || (response.status === 403 ? 'Phiên đăng nhập không hợp lệ. Hãy tải lại trang và đăng nhập.' : 'Không thể thực hiện yêu cầu.'));
 // Cập nhật token sau khi tải phiên, đăng nhập hoặc đăng xuất.
 if (data.csrfToken) csrfToken = data.csrfToken;
 return data as T;
}
