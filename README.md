# Ngạn Tâm Mạc Vấn — Tra giá & Quản lý đơn hàng

Website tra giá CNY sang VND, theo dõi vận chuyển, quản lý đơn hàng và nhân viên. Backend dùng **Django (Python)**; frontend dùng **React, TypeScript & Tailwind CSS (Vite)**.

Xem [hướng dẫn tài khoản, phân quyền và chức năng](frontend/README.md). Frontend hiện chỉ giữ các trang của hệ thống đặt hàng. Backend `drl_app` vẫn được Django sử dụng qua cấu hình tài khoản, API và WebSocket nên được giữ cùng migrations và dữ liệu.

---

## Cài đặt và Khởi chạy Dự án

### 1. Chuẩn bị môi trường
Yêu cầu hệ thống đã cài đặt sẵn:
- **Python 3.10+** (dùng Python 3.10-3.13 nếu cần tính năng Face ID)
- **Node.js 18+** & **pnpm** (hoặc npm/yarn)

---

### 2. Khởi chạy Django Backend

Di chuyển vào thư mục dự án chứa file `requirements.txt`:
```bash
# Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# Khởi tạo/cập nhật cơ sở dữ liệu và chạy backend
python backend/manage.py migrate
python backend/manage.py runserver
```

Backend sẽ chạy tại: [http://localhost:8000/](http://localhost:8000/)

### 3. Khởi chạy React Frontend (Vite)

Mở một cửa sổ Terminal mới:

```bash
cd frontend

# Cài đặt các package dependencies bằng pnpm (hoặc npm install)
pnpm install

# Khởi chạy ứng dụng ở chế độ development
pnpm dev
```
Frontend sẽ chạy tại: [http://localhost:8080/](http://localhost:8080/) hoặc cổng Vite thông báo.

---

