import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { vi } from "vitest";
import App from "../App";
import OrderManagement from "../pages/OrderManagement";
import OrderContact from "../components/OrderContact";
import { api, Account } from "../lib/order-api";
import {
  defaultSettings,
  normalizeCode,
  quote,
  statuses,
  validSettings,
} from "../lib/shop";
vi.mock("../lib/order-api", () => ({ api: vi.fn() }));
const mockedApi = vi.mocked(api);
const admin: Account = {
  id: "1",
  username: "boss",
  fullName: "Admin",
  role: "admin",
};
const employee: Account = {
  id: "2",
  username: "staff",
  fullName: "Nhân viên",
  role: "employee",
};
const shipment = {
  id: "1",
  code: "CN123",
  trackingCode: "YD123",
  buyerName: "Nguyễn An",
  name: "Kiện quần áo",
  status: 3,
  note: "",
  updatedAt: "2026-10-27T10:00:00Z",
};
it("totals net receipts across filtered months and excludes orders without a price", async () => {
  mockedApi.mockResolvedValueOnce({ items: [
    { ...shipment, cnyPrice: '100', sharedFee: 5000 },
    { ...shipment, id: '2', code: 'OTHER', buyerName: 'Bình', cnyPrice: '50', sharedFee: 2000, createdAt: '2026-09-01T00:00:00Z' },
    { ...shipment, id: '3', code: 'MISSING', cnyPrice: null },
  ] });
  render(<OrderManagement settings={defaultSettings} onChange={() => {}} />);
  await screen.findByText('CN123');
  fireEvent.click(screen.getByRole('button', { name: 'Xóa bộ lọc' }));
  const summary = screen.getByRole('status', { name: 'Tổng thực nhận theo bộ lọc' });
  expect(within(summary).getByText('3 đơn theo bộ lọc hiện tại')).toBeInTheDocument();
  expect(within(summary).getByText('Chưa tính 1 đơn chưa có giá tệ.')).toBeInTheDocument();
  expect(screen.getByTestId('orders-net-total').textContent).toContain('28.000');
  fireEvent.change(screen.getByLabelText('Tìm bản ghi'), { target: { value: 'OTHER' } });
  expect(screen.getByTestId('orders-net-total').textContent).toContain('18.000');
  fireEvent.change(screen.getByLabelText('Tìm bản ghi'), { target: { value: 'nothing' } });
  expect(screen.getByTestId('orders-net-total').textContent).toMatch(/^0\s*₫$/);
});
function setup(user: Account | null = null) {
  mockedApi.mockImplementation(async (path, method) => {
    if (path === "session/") return { user };
    if (path === "contact/") return { url: "https://example.com/profile" };
    if (path === "pricing/" && (!method || method === "GET"))
      return structuredClone(defaultSettings);
    if (path === "shipments/" && !method) return { items: [] };
    if (path === "employees/" && !method) return { items: [employee] };
    if (path.startsWith("lookup/")) return { items: [shipment] };
    return {};
  });
  render(<App />);
}
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-09-30T18:00:00Z"));
});
afterEach(() => {
  vi.useRealTimers();
  cleanup();
  window.history.replaceState(null, "", "/");
  vi.resetAllMocks();
});
it("uses one tier with inclusive lower bounds, and rounds percent fees", () => {
  expect(quote(99.99, defaultSettings)?.fee).toBe(20000);
  expect(quote(100, defaultSettings)).toMatchObject({
    base: 360000,
    fee: 15000,
    total: 375000,
  });
  expect(quote(500, defaultSettings)?.fee).toBe(10000);
  expect(quote(0, defaultSettings)).toBeNull();
  expect(quote(NaN, defaultSettings)).toBeNull();
  expect(
    quote(1.23, {
      rate: 3601,
      tiers: [{ from: 0, type: "percent", value: 5 }],
    }),
  ).toMatchObject({ base: 4430, fee: 221, total: 5000 });
  expect(
    validSettings({
      rate: 3600,
      tiers: [
        { from: 0, type: "fixed", value: 1 },
        { from: 0, type: "fixed", value: 2 },
      ],
    }),
  ).toBe(false);
  expect(normalizeCode(" cn-123 ")).toBe("CN-123");
});
it("guests can quote but cannot access management buttons", async () => {
  setup();
  await screen.findByRole("button", { name: "Đăng nhập" });
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Điều hướng chính' })).getByRole("link", { name: "Tra giá" }));
  await waitFor(() =>
    expect(screen.getByTestId("quote-total")).toHaveTextContent("375.000"),
  );
  expect(
    screen.queryByRole("link", { name: "Quản lý đơn" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Quản lý sản phẩm' })).not.toBeInTheDocument();
  expect(screen.queryByText('Đăng nhập để chỉnh')).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Chỉnh tỷ giá và thang tiền công" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Tên đăng nhập"), {
    target: { value: "staff" },
  });
  fireEvent.change(within(dialog).getByLabelText("Mật khẩu"), {
    target: { value: "secret" },
  });
  mockedApi.mockResolvedValueOnce({ user: employee });
  fireEvent.click(within(dialog).getByRole("button", { name: "Đăng nhập" }));
  await screen.findByRole("link", { name: "Quản lý đơn" });
  expect(screen.getByRole('link', { name: 'Quản lý sản phẩm' })).toBeInTheDocument();
  expect(mockedApi).toHaveBeenCalledWith("login/", "POST", {
    username: "staff",
    password: "secret",
  });
  expect(
    screen.queryByRole("link", { name: "Nhân viên" }),
  ).not.toBeInTheDocument();
});
it("employee saves shared pricing through authenticated API", async () => {
  setup(employee);
  await screen.findByRole('link', { name: 'Quản lý sản phẩm' });
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Điều hướng chính' })).getByRole("link", { name: "Tra giá" }));
  await screen.findByRole("button", {
    name: "Chỉnh tỷ giá và thang tiền công",
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Chỉnh tỷ giá và thang tiền công" }),
  );
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Tỷ giá VND cho 1 CNY"), {
    target: { value: "4000" },
  });
  mockedApi.mockResolvedValueOnce({ ...defaultSettings, rate: 4000 });
  fireEvent.click(within(dialog).getByRole("button", { name: "Lưu cấu hình" }));
  await waitFor(() =>
    expect(screen.getByTestId("quote-total")).toHaveTextContent("415.000"),
  );
  expect(mockedApi).toHaveBeenCalledWith(
    "pricing/",
    "PUT",
    expect.objectContaining({ rate: 4000 }),
  );
});
it("admin creates and deletes employees", async () => {
  setup(admin);
  await screen.findByRole("link", { name: "Nhân viên" });
  fireEvent.click(screen.getByRole("link", { name: "Nhân viên" }));
  await screen.findByRole("button", { name: "Xóa nhân viên staff" });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Tạo nhân viên" })).toBeEnabled(),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const dialog = screen.getByRole("main");
  fireEvent.change(within(dialog).getByLabelText("Họ và tên"), {
    target: { value: "An" },
  });
  fireEvent.change(within(dialog).getByLabelText("Tên đăng nhập"), {
    target: { value: "newstaff" },
  });
  fireEvent.change(within(dialog).getByLabelText("Mật khẩu ban đầu"), {
    target: { value: "New-password-83" },
  });
  mockedApi.mockResolvedValueOnce({
    id: "3",
    username: "newstaff",
    fullName: "An",
    role: "employee",
  });
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Tạo nhân viên" }),
  );
  await screen.findByRole("button", { name: "Xóa nhân viên newstaff" });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  fireEvent.click(
    screen.getByRole("button", { name: "Xóa nhân viên newstaff" }),
  );
  await waitFor(() =>
    expect(mockedApi).toHaveBeenCalledWith("employees/3/", "DELETE"),
  );
  vi.restoreAllMocks();
});
it("employee can add order and tracking codes, public lookup shows all stages", async () => {
  setup(employee);
  await screen.findByRole("link", { name: "Quản lý đơn" });
  fireEvent.click(screen.getByRole("link", { name: "Quản lý đơn" }));
  await waitFor(() => expect(mockedApi).toHaveBeenCalledWith("shipments/"));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Thêm mã đơn" })).toBeEnabled(),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Thêm mã đơn" }));
  const dialog = screen.getByRole("main");
  fireEvent.change(within(dialog).getByLabelText("Mã đơn hàng"), {
    target: { value: "cn123" },
  });
  fireEvent.change(within(dialog).getByLabelText("Mã vận đơn Trung"), {
    target: { value: "YD123" },
  });
  fireEvent.change(within(dialog).getByLabelText("Tên hàng / nội dung đơn"), {
    target: { value: shipment.name },
  });
  fireEvent.change(within(dialog).getByLabelText("Tên người mua hàng"), {
    target: { value: shipment.buyerName },
  });
  mockedApi.mockResolvedValueOnce(shipment);
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Lưu trạng thái" }),
  );
  await screen.findByRole("button", { name: "Sửa CN123" });
  expect(mockedApi).toHaveBeenCalledWith(
    "shipments/",
    "POST",
    expect.objectContaining({
      code: "CN123",
      trackingCode: "YD123",
      buyerName: shipment.buyerName,
    }),
  );
  fireEvent.click(screen.getByRole("link", { name: "Kiểm tra hàng" }));
  expect(screen.queryByTestId("quote-total")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Mã đơn Trung hoặc mã vận đơn"), {
    target: { value: "yd123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Tra cứu" }));
  await screen.findByRole("heading", { name: shipment.name });
  expect(mockedApi).toHaveBeenCalledWith("lookup/?code=YD123");
  const timeline = screen.getByRole("list");
  statuses.forEach((s) =>
    expect(within(timeline).getByText(s)).toBeInTheDocument(),
  );
  expect(within(timeline).getByText("Kho Việt").closest("li")).toHaveClass(
    "current",
  );
});
it("blocks guests opening the management URL without requesting orders", async () => {
  window.history.replaceState(null, "", "/#/quan-ly-don");
  setup();
  await screen.findByTestId("quote-total");
  expect(
    screen.queryByRole("link", { name: "Quản lý đơn" }),
  ).not.toBeInTheDocument();
  expect(mockedApi).not.toHaveBeenCalledWith("shipments/");
});
it("admin can open the management URL and loses access after logout", async () => {
  window.history.replaceState(null, "", "/#/quan-ly-don");
  setup(admin);
  await screen.findByRole("heading", { name: "Quản lý đơn & mã vận đơn" });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Thêm mã đơn" })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
  await screen.findByTestId("quote-total");
  expect(
    screen.queryByRole("button", { name: "Thêm mã đơn" }),
  ).not.toBeInTheDocument();
});
it.each([null, employee])(
  "blocks non-admin access to the employees URL (%s)",
  async (user) => {
    window.history.replaceState(null, "", "/#/nhan-vien");
    setup(user);
    await screen.findByTestId("quote-total");
    expect(
      screen.queryByRole("link", { name: "Nhân viên" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Tạo nhân viên" }),
    ).not.toBeInTheDocument();
    expect(mockedApi).not.toHaveBeenCalledWith("employees/");
  },
);
it("admin can open the employees URL and loses access after logout", async () => {
  window.history.replaceState(null, "", "/#/nhan-vien");
  setup(admin);
  await screen.findByRole("heading", { name: "Quản lý nhân viên" });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Tạo nhân viên" })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
  await screen.findByTestId("quote-total");
  expect(
    screen.queryByRole("button", { name: "Tạo nhân viên" }),
  ).not.toBeInTheDocument();
});
it("groups orders by creation month in Vietnam and searches across tables", async () => {
  mockedApi.mockResolvedValueOnce({
    items: [
      {
        ...shipment,
        createdAt: "2026-09-30T18:00:00Z",
        updatedAt: "2026-12-01T00:00:00Z",
      },
      {
        ...shipment,
        id: "2",
        code: "SEP001",
        createdAt: "2026-09-15T00:00:00Z",
      },
      {
        ...shipment,
        id: "3",
        code: "OLD001",
        createdAt: "2025-10-01T00:00:00Z",
      },
    ],
  });
  render(<OrderManagement onChange={() => {}} />);
  const october = await screen.findByRole("table", {
    name: "Tháng 10/2026 · 1 đơn",
  });
  expect(within(october).getByText("CN123")).toBeInTheDocument();
  expect(screen.getByLabelText("Tháng")).toHaveValue("10");
  expect(screen.getByLabelText("Năm")).toHaveValue(2026);
  expect(screen.getAllByRole("table")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Tìm bản ghi"), {
    target: { value: "nguyễn an" },
  });
  expect(screen.getAllByRole("table")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Tìm bản ghi"), {
    target: { value: "yd123" },
  });
  expect(screen.getAllByRole("table")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
  expect(
    screen
      .getAllByRole("table")
      .map((table) => table.querySelector("caption")?.textContent),
  ).toEqual([
    "Tháng 10/2026 · 1 đơn",
    "Tháng 09/2026 · 1 đơn",
    "Tháng 10/2025 · 1 đơn",
  ]);
  expect(
    within(october).getByRole("columnheader", { name: "Mã đơn hàng" }),
  ).toBeInTheDocument();
  expect(
    within(october).getByRole("columnheader", { name: "Mã vận đơn Trung" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Tìm bản ghi"), {
    target: { value: "SEP001" },
  });
  expect(screen.getAllByRole("table")).toHaveLength(1);
  expect(
    screen.getByRole("table", { name: "Tháng 09/2026 · 1 đơn" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Tháng"), { target: { value: "10" } });
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Tìm bản ghi"), {
    target: { value: "" },
  });
  expect(screen.getAllByRole("table")).toHaveLength(2);
  fireEvent.change(screen.getByLabelText("Năm"), { target: { value: "2025" } });
  expect(screen.getAllByRole("table")).toHaveLength(1);
  expect(
    screen.getByRole("table", { name: "Tháng 10/2025 · 1 đơn" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Năm"), { target: { value: "2030" } });
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(
    screen.getByText("Không có đơn hàng phù hợp với bộ lọc và từ khóa."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
  expect(screen.getAllByRole("table")).toHaveLength(3);
  fireEvent.change(screen.getByLabelText("Năm"), { target: { value: "2026" } });
  expect(screen.getAllByRole("table")).toHaveLength(2);
});
it("admin can save the public ordering link", async () => {
  mockedApi.mockResolvedValueOnce({ url: "https://example.com/old" });
  render(<OrderContact isAdmin />);
  await screen.findByRole("link", {
    name: "Nhắn tin qua trang cá nhân để được tư vấn",
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Chỉnh liên kết đặt hàng" }),
  );
  fireEvent.change(screen.getByLabelText("Liên kết trang cá nhân"), {
    target: { value: "https://example.com/new" },
  });
  mockedApi.mockResolvedValueOnce({ url: "https://example.com/new" });
  fireEvent.click(screen.getByRole("button", { name: "Lưu liên kết" }));
  await waitFor(() =>
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "https://example.com/new",
    ),
  );
  expect(mockedApi).toHaveBeenCalledWith("contact/", "PUT", {
    url: "https://example.com/new",
  });
});
it("visitors see the order link without edit controls", async () => {
  mockedApi.mockResolvedValueOnce({ url: "https://example.com/profile" });
  render(<OrderContact isAdmin={false} />);
  expect(await screen.findByRole("link")).toHaveAttribute(
    "href",
    "https://example.com/profile",
  );
  expect(
    screen.queryByRole("button", { name: "Chỉnh liên kết đặt hàng" }),
  ).not.toBeInTheDocument();
});
it("shows API failure instead of a fabricated quote", async () => {
  mockedApi.mockRejectedValue(new Error("Không kết nối được API"));
  render(<App />);
  await screen.findAllByRole("alert");
  expect(screen.queryByTestId("quote-total")).not.toBeInTheDocument();
});
