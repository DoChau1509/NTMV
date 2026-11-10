# Ngạn Tâm Mạc Vấn — Tra giá, theo dõi hàng & phân quyền

## Chạy dự án

Từ thư mục gốc, khởi tạo cơ sở dữ liệu và tạo admin đầu tiên:

```sh
python backend/manage.py migrate
python backend/manage.py create_order_admin --username admin --name "Quản trị viên"
```

Lệnh tạo admin sẽ hỏi mật khẩu hai lần, không hiển thị ký tự ra màn hình. Mật khẩu tối thiểu 8 ký tự, không phổ biến hoặc chỉ chứa số. Không có tài khoản hay mật khẩu mặc định. Tài khoản Ngạn Tâm Mạc Vấn tách biệt với tài khoản quản lý sinh viên cũ.

Chạy backend trong một terminal:

```sh
python backend/manage.py runserver 127.0.0.1:8000
```

Chạy frontend trong terminal khác:

```sh
npm --prefix frontend run dev
```

Mở http://localhost:8080 (hoặc cổng Vite báo). Vite chuyển `/api/order/` tới Django ở cổng 8000. Khi triển khai cần chuyển tiếp đường dẫn này tới Django trên cùng tên miền; cấu hình cookie HTTPS, host và Django production tương ứng.

## Quyền sử dụng

| Chức năng | Khách chưa đăng nhập | Nhân viên | Admin |
|---|---|---|---|
| Tra giá, tra trạng thái bằng mã chính xác | Có | Có | Có |
| Xem danh sách và thêm/sửa/xóa đơn | Không | Có | Có |
| Thêm/sửa/xóa mã vận đơn trên đơn | Không | Có | Có |
| Sửa tỷ giá và thêm/sửa/xóa bậc công | Không | Có | Có |
| Xem, tạo và xóa tài khoản nhân viên | Không | Không | Có |

Admin đăng nhập rồi chọn **Nhân viên** để tạo hoặc xóa tài khoản. API luôn tạo vai trò nhân viên, không chấp nhận nâng quyền từ dữ liệu gửi lên. Không cho xóa admin qua màn hình nhân viên. Xóa nhân viên giữ nguyên dữ liệu đơn hàng và chặn ngay các yêu cầu tiếp theo từ phiên của tài khoản đó.

Mật khẩu lưu dạng băm theo Django; đăng nhập dùng phiên máy chủ với cookie HttpOnly và CSRF cho các thao tác ghi. Phiên hết hạn sau 8 giờ. Giới hạn 10 lần đăng nhập sai trong 5 phút theo IP và tên đăng nhập; dùng cache Django (mặc định là bộ nhớ từng tiến trình).

## Tra giá

Giá xuất ra = tiền CNY × tỷ giá + công theo bậc. Tiền hàng và công được làm tròn riêng đến đồng trước khi cộng. Chưa gồm phí vận chuyển và phụ phí khác.

Đăng nhập và chọn nút cài đặt trên thẻ Tra giá. Mỗi bậc tính từ ngưỡng CNY của nó đến dưới ngưỡng kế tiếp; bậc đầu từ 0, bậc cuối không có giới hạn trên. Áp dụng đúng một bậc, không cộng dồn. Công cố định bằng VND hoặc phần trăm tiền hàng quy đổi. Tỷ giá và mức công ban đầu là số mẫu nhập thủ công, không lấy tỷ giá trực tiếp.

## Đơn hàng và mã vận đơn

Chọn **Quản lý đơn** để thêm, sửa hoặc xóa bản ghi. Mã đơn Trung bắt buộc và không trùng; mã vận đơn có thể để trống hoặc bổ sung/xóa sau. Mã được chuẩn hóa chữ hoa và bỏ khoảng trắng đầu/cuối. Nếu một mã vận đơn khớp nhiều đơn, người tra cứu có thể chọn đơn muốn xem.

Sáu trạng thái theo thứ tự:

1. Đã mua
2. Có mã đơn Trung
3. Kho Trung
4. Kho Việt
5. Đã kiểm
6. Đã ship hàng

Nhân viên nhập trạng thái thủ công, chưa tự kết nối hãng vận chuyển. Các bước trước trạng thái hiện tại được hiển thị đã qua theo quy trình, không phải nhật ký thời gian từng chặng.

## Quản lý sản phẩm theo đợt gom

Admin và nhân viên chọn **Quản lý sản phẩm** (`#/quan-ly-san-pham`) để tạo thư mục đợt gom với tên, ngày bắt đầu và ngày kết thúc. Trong mỗi đợt, thêm các đơn khách; mỗi đơn có tên khách, link trang cá nhân (nếu có), tổng tiền đã thanh toán bằng VND và từ 1 đến 100 mặt hàng.

Hai ô **Tìm kiếm đợt gom** và **Tìm kiếm khách hàng** có thể kết hợp, không phân biệt hoa/thường hoặc dấu tiếng Việt. Tìm khách riêng sẽ lọc các đợt có khách đó và chỉ hiện đơn của khách phù hợp trong đợt đang chọn. Mỗi lần hiển thị tối đa 4 đợt gom; dùng nút **Lên / Xuống** để chuyển nhóm. Từ khóa khách được giữ khi chọn đợt khác, và thay đổi tìm kiếm sẽ trở về nhóm kết quả đầu tiên.

Mỗi mặt hàng lưu tên, số lượng nguyên dương, đơn giá CNY (tối đa 2 chữ số thập phân), trạng thái thanh toán **Thanh toán đủ / Cọc / Còn cân nặng** và tình trạng hàng **Đã mua / Đã về / Đã ship**. Tổng tệ của mặt hàng bằng số lượng × đơn giá; tổng đơn là tổng các mặt hàng, không quy đổi hoặc trừ trực tiếp tiền VND khỏi CNY.

Mỗi đơn có thêm **Tiền còn lại (VND)** để nhân viên nhập sau khi chốt giá và phụ phí. Số tiền này lưu riêng với tổng CNY và tiền đã thanh toán, không tự quy đổi theo tỷ giá. Để trống khi chưa xác định (hiện **Chưa cập nhật**), nhập `0` khi không còn khoản phải trả. Đơn cũ mặc định chưa cập nhật; nhập hoặc sửa trong biểu mẫu đơn khách.

Món **Cọc** bắt buộc nhập ngày thanh toán nốt. Cảnh báo hiển thị bên ngoài danh sách mặt hàng của đơn khách vào ngày trước hạn, trong ngày đến hạn và sau hạn, theo ngày lịch Việt Nam. Đổi sang **Thanh toán đủ** hoặc **Còn cân nặng** sẽ gỡ hạn và ngừng cảnh báo cọc. Số tiền đã trả của đơn được cập nhật riêng, không tự đổi trạng thái từng món.

Dữ liệu được lưu trong các bảng `Gathering`, `GatheringOrder`, `GatheringItem` của Django; API yêu cầu phiên admin/nhân viên và CSRF khi ghi. Chạy `python backend/manage.py migrate` khi cập nhật môi trường khác. Xóa đơn sẽ xóa các mặt hàng sau khi xác nhận; chỉ xóa được đợt gom khi đã xóa hết đơn khách.

Trang này quản lý riêng với trang **Quản lý đơn** và chưa tự tạo bản ghi tra vận đơn. File Excel xuất từ trang Quản lý đơn hiện chỉ chứa dữ liệu của trang đó; để sao lưu cả đợt gom cần sao lưu database.

## Lưu trữ và dữ liệu cũ

Tài khoản, đơn và cấu hình giá lưu trong SQLite của Django, dùng chung giữa các thiết bị truy cập cùng máy chủ. Frontend không lưu mật khẩu hoặc quyền đăng nhập trong localStorage. Dữ liệu `moc-shipments` và `moc-lookup-settings` từ phiên bản cục bộ cũ vẫn giữ trong trình duyệt, chưa tự nhập vào máy chủ. Các API quản lý mới ở `/api/order/` dùng xác thực riêng, không chấp nhận mock token của hệ thống sinh viên cũ.

## Kiểm tra

```sh
python backend/manage.py test order_app --noinput
npm --prefix frontend test
npm --prefix frontend run build
```

Kiểm tra kiểu cho giao diện Ngạn Tâm Mạc Vấn đang chạy: `npm --prefix frontend run typecheck:order`. Lệnh TypeScript toàn bộ `tsconfig.app.json` vẫn gặp các lỗi có sẵn ở mã quản lý sinh viên cũ (các trang không được ứng dụng mới sử dụng); cấu hình `tsconfig.order.json` kiểm tra giao diện hiện tại và các phụ thuộc được import.
