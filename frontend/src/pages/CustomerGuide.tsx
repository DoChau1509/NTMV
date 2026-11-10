import { ArrowRight, BookOpen, Calculator, MessageCircle, PackageSearch } from 'lucide-react';
import { Link } from 'react-router-dom';
import OrderContact from '../components/OrderContact';
import { money, quote, Settings, statuses } from '../lib/shop';

const journeyNotes = [
  'Đơn đã được mua theo thông tin xác nhận.',
  'Đã bổ sung thông tin mã đơn Trung.',
  'Hàng đã tới kho Trung Quốc.',
  'Hàng đã tới kho Việt Nam.',
  'Hàng đã được kiểm tra.',
  'Hàng đã được gửi đi để giao cho bạn.',
];

export default function CustomerGuide({ settings, ready }: { settings: Settings; ready: boolean }) {
  const example = ready ? quote(100, settings) : null;
  function jump(id: string) {
    const heading = document.getElementById(id);
    heading?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    heading?.focus({ preventScroll: true });
  }
  return <section className="tool-card customer-guide">
    <div className="card-heading">
      <span className="tool-icon"><BookOpen size={22} /></span>
      <div><span className="eyebrow">DÀNH CHO KHÁCH HÀNG</span><h2>Hướng dẫn đặt hàng & tra cứu</h2></div>
    </div>
    <p className="guide-intro">
      Từ lúc xem giá đến khi nhận hàng,
      bạn có thể bắt đầu theo các bước dưới đây.
      Tra giá và kiểm tra hành trình đều không cần đăng nhập.
    </p>

    <nav className="guide-topics" aria-label="Mục hướng dẫn">
      <button type="button" onClick={() => jump('guide-pricing')}><Calculator size={20} /><span><b>01 · Tra giá</b><small>Biết trước tiền hàng & tiền công</small></span><ArrowRight size={16} /></button>
      <button type="button" onClick={() => jump('guide-ordering')}><MessageCircle size={20} /><span><b>02 · Đặt hàng</b><small>Chuẩn bị thông tin để gửi đơn</small></span><ArrowRight size={16} /></button>
      <button type="button" onClick={() => jump('guide-tracking')}><PackageSearch size={20} /><span><b>03 · Theo dõi</b><small>Tra hành trình bằng mã đơn</small></span><ArrowRight size={16} /></button>
    </nav>

    <div className="guide-grid">
      <section className="guide-block" aria-labelledby="guide-pricing">
        <h3 id="guide-pricing" tabIndex={-1}><span>01</span>Cách tra giá sản phẩm</h3>
        <ol className="guide-steps">
          <li>
            Mở trang <Link to="/tra-gia">Tra giá</Link> và nhập giá sản phẩm bằng Nhân dân tệ (CNY).
          </li>
          <li>
            Xem tiền hàng quy đổi, tiền công và giá sản phẩm.
            Hệ thống chọn một bậc công theo số tệ, không cộng dồn các bậc.
          </li>
          <li>
            Gửi link sản phẩm cho nhân viên để xác nhận giá và các khoản phát sinh trước khi đặt.
          </li>
        </ol>
        {example && <aside className="guide-example" aria-label="Ví dụ tra giá">
          <span>VÍ DỤ THEO BẢNG GIÁ HIỆN TẠI</span>
          <p>Sản phẩm <b>100 CNY</b> · tỷ giá {money(settings.rate)}/CNY</p>
          <dl><div><dt>Tiền hàng quy đổi</dt><dd>{money(example.base)}</dd></div><div><dt>Tiền công</dt><dd>{money(example.fee)}</dd></div>
            {example.roundingAdjustment > 0 && <div><dt>Phần làm tròn</dt><dd>{money(example.roundingAdjustment)}</dd></div>}
            <div className="guide-example-total"><dt>Giá sản phẩm</dt><dd>{money(example.total)}</dd></div>
          </dl>
        </aside>}
        <p className="guide-note">
          Giá tra cứu đã gồm tiền công, chưa gồm phí cân, phí nội địa hoặc phụ phí khác.
          Giá được làm tròn lên đến 1.000đ.
        </p>
        <Link className="secondary" to="/tra-gia">Tra giá ngay <ArrowRight size={16} /></Link>
      </section>

      <section className="guide-block" aria-labelledby="guide-ordering">
        <h3 id="guide-ordering" tabIndex={-1}><span>02</span>Cách đặt hàng</h3>
        <ol className="guide-steps">
          <li>Chuẩn bị link sản phẩm, ảnh hoặc mô tả mẫu, màu, kích thước và số lượng cần mua.</li>
          <li>Nhắn tin qua liên kết liên hệ ở cuối trang để được xác nhận sản phẩm, giá, phí và cách thanh toán.</li>
          <li>Gửi tên người nhận, số điện thoại và địa chỉ giao hàng trực tiếp cho nhân viên khi xác nhận đơn.</li>
          <li>Thanh toán hoặc đặt cọc theo nội dung đã thống nhất. Giữ lại biên nhận và nhận mã đơn từ nhân viên để tra cứu.</li>
        </ol>
        <label className="guide-template">Mẫu thông tin gửi đặt hàng
          <textarea readOnly rows={7} value={'Link sản phẩm: …\nMẫu / màu / kích thước: …\nSố lượng: …\nTên người nhận: …\nSố điện thoại: …\nĐịa chỉ giao hàng: …\nGhi chú: …'} />
        </label>
        <p className="guide-note">Đơn được nhân viên xác nhận và tạo sau khi trao đổi. Liên hệ nhân viên nếu cần đổi mẫu, sửa thông tin hoặc hủy đơn.</p>
      </section>

      <section className="guide-block" aria-labelledby="guide-tracking">
        <h3 id="guide-tracking" tabIndex={-1}><span>03</span>Cách kiểm tra hành trình</h3>
        <ol className="guide-steps">
          <li>Mở <Link to="/kiem-tra-hang">Kiểm tra hàng</Link>, nhập đầy đủ mã đơn hoặc mã vận đơn Trung do nhân viên cung cấp.</li>
          <li>Bấm “Tra cứu” để xem trạng thái hàng, thông tin thanh toán và thời điểm cập nhật.</li>
          <li>Nếu một mã vận đơn có nhiều đơn, chọn đúng đơn cần xem trong kết quả.</li>
        </ol>
        <details className="guide-journey"><summary>Các trạng thái hành trình có nghĩa gì?</summary>
          <dl>{statuses.map((status, index) => <div key={status}><dt>{index + 1}. {status}</dt><dd>{journeyNotes[index]}</dd></div>)}</dl>
        </details>
        <p className="guide-note">Hành trình được nhân viên cập nhật. Nếu chưa thấy đơn hoặc thông tin chưa thay đổi, kiểm tra lại mã và liên hệ nhân viên để được hỗ trợ.</p>
        <Link className="secondary" to="/kiem-tra-hang">Kiểm tra hàng <ArrowRight size={16} /></Link>
      </section>

      <section className="guide-block" aria-labelledby="guide-payment">
        <h3 id="guide-payment" tabIndex={-1}><span>04</span>Thanh toán & phụ phí</h3>
        <p>Tổng tiền đơn gồm tiền hàng theo tỷ giá đã chốt, tiền công và phụ phí phát sinh.</p>
        <ul className="guide-steps">
          <li><b>Phí cân:</b> khoản phí theo cân nặng được nhân viên xác nhận khi có thông tin hàng.</li>
          <li><b>Phí nội địa:</b> chi phí vận chuyển nội địa được thông báo cho từng đơn.</li>
          <li><b>Phí khác:</b> các khoản phát sinh khác được xác nhận cùng nhân viên.</li>
        </ul>
        <aside className="guide-example"><b>Số còn cần trả</b><p>Tổng tiền đơn − số đã thanh toán sau hoàn tiền, làm tròn lên đến 1.000đ.</p><p>Ví dụ: còn 56.790đ thì thanh toán 57.000đ.</p></aside>
        <p>Khi thấy trạng thái “Cọc” hoặc “Còn phụ phí”, hãy kiểm tra số tiền còn lại hiển thị và xác nhận với nhân viên trước khi thanh toán tiếp.</p>
        <p className="guide-note">
          Gửi biên nhận hoặc mã giao dịch để nhân viên ghi nhận khoản thu.
          Nếu số tiền chưa khớp, vui lòng liên hệ để đối soát;
          trạng thái thanh toán có thể được nhân viên cập nhật riêng.
        </p>
      </section>
    </div>

    <section className="guide-faq" aria-labelledby="guide-faq-title">
      <h3 id="guide-faq-title">Câu hỏi thường gặp</h3>
      <details>
        <summary>Vì sao giá tra cứu khác với đơn đã đặt?</summary>
        <p>Trang tra giá dùng bảng giá hiện tại, còn đơn đã tạo giữ tỷ giá
          và bảng công đã chốt. Tổng tiền đơn còn có thể gồm phụ phí được thông báo sau đó.</p>
      </details>
      <details>
        <summary>Tôi chưa có mã đơn hoặc tra cứu không thấy?</summary>
        <p>Nhờ nhân viên cung cấp mã đơn hoặc mã vận đơn Trung. Kiểm tra đã nhập đủ mã, không dùng link sản phẩm hoặc tên người mua để tra cứu.</p></details>
      <details>
        <summary>Bao lâu hàng về? Có thể đổi hoặc hoàn tiền không?</summary><p>Liên hệ nhân viên để được xác nhận thời gian dự kiến và điều kiện áp dụng cho đơn cụ thể. Trang tra cứu hiển thị trạng thái hiện có; không phải lịch hẹn giao hàng.</p></details>
    </section>
    <OrderContact isAdmin={false} />
  </section>;
}
