import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import ProductManagement from '../pages/ProductManagement';
import { api } from '../lib/order-api';
import { deadlineWarning, formatCny, Gathering, GatheringItem, orderCents, orderVnd, remainingVnd } from '../lib/gatherings';

vi.mock('../lib/order-api', () => ({ api: vi.fn() }));
afterEach(() => { vi.clearAllMocks(); vi.useRealTimers(); });
const item: GatheringItem = { id: '1', name: 'Áo', note: '', quantity: 3, unitPrice: '0.10', unitPriceVnd: null, depositDueOn: '2026-11-07', status: 'bought' };

it('calculates exact CNY totals and warns one calendar day ahead in Vietnam', () => {
  expect(formatCny(orderCents([item, { ...item, quantity: 1, unitPrice: '0.20' }]))).toBe('¥ 0,50');
  expect(formatCny(orderCents([{ ...item, quantity: 1, unitPrice: '.5' }, { ...item, quantity: 2, unitPrice: '1e2' }]))).toBe('¥ 200,50');
  expect(deadlineWarning(item, new Date('2026-11-05T16:59:00Z'))).toBeNull();
  expect(deadlineWarning(item, new Date('2026-11-05T17:00:00Z'))).toContain('ngày mai');
  expect(deadlineWarning(item, new Date('2026-11-07T01:00:00Z'))).toContain('hôm nay');
  expect(deadlineWarning(item, new Date('2026-11-08T01:00:00Z'))).toContain('Quá hạn 1 ngày');
  expect(deadlineWarning(item, new Date('2026-11-08T01:00:00Z'), 0n)).toBeNull();
  expect(deadlineWarning({ ...item, depositDueOn: null }, new Date('2026-11-08T01:00:00Z'), 100n)).toBeNull();
});

it('recalculates a stale zero balance and saves order payments without per-item payment statuses', async () => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-06T01:00:00Z'));
  const order = { id: '9', gatheringId: '2', customerName: 'Khách An', profileUrl: 'https://example.com/an', paidAmount: 100000, remainingAmount: '0', totalCny: '0.30', items: [{ ...item, unitPriceVnd: 100000, note: 'Màu xanh\nSize M' }], updatedAt: '' };
  vi.mocked(api).mockResolvedValueOnce({ items: [{ id: '2', name: 'Gom tháng 11', startsOn: '2026-11-01', endsOn: '2026-11-30', orders: [order] }] });
  render(<ProductManagement />);
  const reminder = await screen.findByRole('status', { name: 'Nhắc thanh toán của Khách An' });
  expect(reminder).toHaveTextContent('Đến hạn ngày mai');
  const details = screen.getByText('Xem 1 mặt hàng').closest('details');
  expect(details).not.toHaveAttribute('open');
  expect(details).not.toContainElement(reminder);
  expect(screen.getByText(/^Tiền còn lại:/)).toHaveTextContent(/200\.000/);
  expect(screen.getByRole('link', { name: /Trang cá nhân/ })).toHaveAttribute('href', 'https://example.com/an');
  fireEvent.click(screen.getByText('Xem 1 mặt hàng'));
  expect(screen.queryByRole('columnheader', { name: 'Thanh toán', exact: true })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Sửa đơn/ }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).queryByLabelText('Thanh toán', { exact: true })).not.toBeInTheDocument();
  expect(within(dialog).getByLabelText('Ghi chú sản phẩm')).toHaveValue('Màu xanh\nSize M');
  fireEvent.change(within(dialog).getByLabelText('Ghi chú sản phẩm'), { target: { value: 'Màu xanh\nSize L' } });
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveAttribute('readonly');
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveDisplayValue(/200\.000/);
  fireEvent.change(within(dialog).getByLabelText('Đã thanh toán (VND)'), { target: { value: '300000' } });
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveDisplayValue(/^0\s*₫$/);
  vi.mocked(api).mockResolvedValueOnce({ ...order, paidAmount: 300000, remainingAmount: '0', items: [{ ...order.items[0], note: 'Màu xanh\nSize L' }] });
  fireEvent.submit(within(dialog).getByRole('button', { name: 'Lưu đơn khách' }).closest('form')!);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(api).toHaveBeenLastCalledWith('gathering-orders/9/', 'PUT', expect.objectContaining({
    paidAmount: 300000, items: [expect.objectContaining({ id: '1', depositDueOn: '2026-11-07', note: 'Màu xanh\nSize L' })],
  }));
  const calls = vi.mocked(api).mock.calls;
  const payload = calls[calls.length - 1][2] as { remainingAmount?: unknown; items: { paymentStatus?: unknown }[] };
  expect(payload).not.toHaveProperty('remainingAmount');
  expect(payload.items[0]).not.toHaveProperty('paymentStatus');
  expect(screen.queryByRole('status', { name: 'Nhắc thanh toán của Khách An' })).not.toBeInTheDocument();
  expect(screen.getByText(/^Tiền còn lại:/)).toHaveTextContent(/^Tiền còn lại: 0\s*₫$/);
  expect(screen.getByText(/Màu xanh\s+Size L/)).toBeInTheDocument();
});

it('shows load errors and retries without pretending the data is empty', async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error('Lỗi tải dữ liệu')).mockResolvedValueOnce({ items: [] });
  render(<ProductManagement />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Lỗi tải dữ liệu');
  expect(screen.getByRole('button', { name: 'Thêm đợt gom' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  expect(await screen.findByText(/Chưa có đợt gom/)).toBeInTheDocument();
});

function gathering(id: number, name: string, customers: string[]): Gathering {
  return { id: String(id), name, startsOn: '2026-11-01', endsOn: '2026-11-30', orders: customers.map((customerName, index) => ({
    id: `${id}-${index}`, gatheringId: String(id), customerName, profileUrl: '', paidAmount: 0, remainingAmount: null, discountAmount: 0, subtotalVnd: null, totalVnd: null, totalCny: '0.30',
    items: [{ ...item, id: `${id}-${index}`, depositDueOn: null }], updatedAt: '',
  })) };
}

it('totals only unbought items across the whole gathering and updates after edits and deletion', async () => {
  const batch = gathering(1, 'Gom tháng 11', ['Khách An', 'Khách Bình']);
  batch.orders[0].items = [
    { ...batch.orders[0].items[0], status: 'not_bought' },
    ...(['bought', 'arrived', 'shipped'] as const).map((status, index) => ({
      ...item, id: `bought-${index}`, quantity: 1, unitPrice: '100.00', status,
    })),
  ];
  batch.orders[1].items = [{ ...batch.orders[1].items[0], status: 'not_bought', quantity: 2, unitPrice: '0.20' }];
  vi.mocked(api).mockResolvedValueOnce({ items: [batch, gathering(2, 'Gom trống', [])] });
  render(<ProductManagement />);
  expect(await screen.findByText('Tổng tệ chưa mua: ¥ 0,70')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Gom trống/ }));
  expect(screen.getByText('Tổng tệ chưa mua: ¥ 0,00')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Gom tháng 11/ }));
  fireEvent.change(screen.getByLabelText('Tìm kiếm khách hàng'), { target: { value: 'Khách An' } });
  expect(screen.queryByRole('heading', { name: 'Khách Bình' })).not.toBeInTheDocument();
  expect(screen.getByText('Tổng tệ chưa mua: ¥ 0,70')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Xem 4 mặt hàng'));
  expect(screen.getByRole('cell', { name: 'Chưa mua', exact: true })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Sửa đơn/ }));
  const dialog = screen.getByRole('dialog');
  const status = within(dialog).getAllByLabelText('Tình trạng hàng')[0];
  expect(status).toHaveValue('not_bought');
  expect(within(status).getByRole('option', { name: 'Chưa mua' })).toBeInTheDocument();
  fireEvent.change(status, { target: { value: 'bought' } });
  const updated = { ...batch.orders[0], items: batch.orders[0].items.map((row, index) => index === 0 ? { ...row, status: 'bought' as const } : row) };
  vi.mocked(api).mockResolvedValueOnce(updated);
  fireEvent.submit(within(dialog).getByRole('button', { name: 'Lưu đơn khách' }).closest('form')!);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(api).toHaveBeenLastCalledWith('gathering-orders/1-0/', 'PUT', expect.objectContaining({
    items: expect.arrayContaining([expect.objectContaining({ id: '1-0', status: 'bought' })]),
  }));
  expect(screen.getByText('Tổng tệ chưa mua: ¥ 0,40')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Xóa tìm kiếm' }));
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(api).mockResolvedValueOnce({});
  fireEvent.click(screen.getByRole('button', { name: 'Xóa đơn của Khách Bình' }));
  await waitFor(() => expect(screen.getByText('Tổng tệ chưa mua: ¥ 0,00')).toBeInTheDocument());
  confirm.mockRestore();
});

it.each([[0, 275000], [100000, 175000], [275000, 0], [300000, 0]])('calculates remaining money for paid amount %s', async (paidAmount, expected) => {
  const batch = gathering(1, 'Gom tháng 11', ['Khách An']);
  batch.orders[0].paidAmount = paidAmount;
  batch.orders[0].discountAmount = 25000;
  batch.orders[0].items[0].unitPriceVnd = 100000;
  vi.mocked(api).mockResolvedValueOnce({ items: [batch] });
  render(<ProductManagement />);
  await screen.findByRole('heading', { name: 'Khách An' });
  expect(screen.getByText(/^Tiền còn lại:/)).toHaveTextContent(new Intl.NumberFormat('vi-VN').format(expected));
  fireEvent.click(screen.getByRole('button', { name: /Sửa đơn/ }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveDisplayValue(new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(expected));
  fireEvent.change(within(dialog).getByLabelText('Giá Việt / món (VND)'), { target: { value: '' } });
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveValue('Chưa đủ giá Việt');
});

it('calculates VND independently of CNY and keeps large totals exact', () => {
  expect(orderVnd([item])).toBeNull();
  expect(orderVnd([{ ...item, unitPriceVnd: 0 }])).toBe(0n);
  expect(orderVnd([{ ...item, unitPriceVnd: 100000 }, { ...item, quantity: 2, unitPriceVnd: 50000 }], 25000)).toBe(375000n);
  expect(orderVnd([{ ...item, quantity: 1000000, unitPriceVnd: 1000000000000 }, { ...item, quantity: 1, unitPriceVnd: 3 }], 1)).toBe(1000000000000000002n);
  expect(orderVnd([{ ...item, unitPriceVnd: 1.5 }])).toBeNull();
  expect(remainingVnd([item], 0, 100000)).toBeNull();
  expect(remainingVnd([{ ...item, quantity: 1000000, unitPriceVnd: 1000000000000 }], 1, 2)).toBe(999999999999999997n);
});

it('creates an order without item payment states and recalculates when adding or removing items', async () => {
  const batch = gathering(1, 'Gom tháng 11', []);
  vi.mocked(api).mockResolvedValueOnce({ items: [batch] });
  render(<ProductManagement />);
  fireEvent.click(await screen.findByRole('button', { name: 'Thêm đơn khách' }));
  const dialog = screen.getByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('Tên khách hàng'), { target: { value: 'Khách An' } });
  fireEvent.change(within(dialog).getByLabelText('Tên mặt hàng'), { target: { value: 'Áo' } });
  fireEvent.change(within(dialog).getByLabelText('Giá tệ / món (CNY)'), { target: { value: '12.35' } });
  fireEvent.change(within(dialog).getByLabelText('Giá Việt / món (VND)'), { target: { value: '100000' } });
  fireEvent.change(within(dialog).getByLabelText('Đã thanh toán (VND)'), { target: { value: '20000' } });
  fireEvent.change(within(dialog).getByLabelText('Giảm giá đơn (VND)'), { target: { value: '10000' } });
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveDisplayValue(/70\.000/);
  fireEvent.click(within(dialog).getByRole('button', { name: 'Thêm mặt hàng' }));
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveValue('Chưa đủ giá Việt');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Xóa mặt hàng 2' }));
  expect(within(dialog).getByLabelText('Tiền còn lại (VND)')).toHaveDisplayValue(/70\.000/);
  expect(within(dialog).getByLabelText('Hạn thanh toán nốt')).not.toBeRequired();
  vi.mocked(api).mockResolvedValueOnce({ ...gathering(1, 'Gom tháng 11', ['Khách An']).orders[0],
    paidAmount: 20000, discountAmount: 10000, remainingAmount: '70000',
    items: [{ ...item, quantity: 1, unitPrice: '12.35', unitPriceVnd: 100000, depositDueOn: null }] });
  fireEvent.submit(within(dialog).getByRole('button', { name: 'Lưu đơn khách' }).closest('form')!);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(api).toHaveBeenLastCalledWith('gatherings/1/orders/', 'POST', expect.objectContaining({
    paidAmount: 20000, discountAmount: 10000, items: [expect.objectContaining({ name: 'Áo', unitPriceVnd: 100000, depositDueOn: null })],
  }));
  expect(screen.getByText(/^Tiền còn lại:/)).toHaveTextContent(/70\.000/);
});

it.each([0, 25000, 400000])('saves manually entered VND prices and subtracts the order discount (%s)', async discountAmount => {
  const batch = gathering(1, 'Gom tháng 11', ['Khách An']);
  const order = batch.orders[0];
  order.items.push({ ...order.items[0], id: 'second', name: 'Túi', quantity: 2 });
  vi.mocked(api).mockResolvedValueOnce({ items: [batch] });
  render(<ProductManagement />);
  expect(await screen.findByText(/^Tổng đơn sau giảm/)).toHaveTextContent('Chưa đủ giá Việt');
  fireEvent.click(screen.getByRole('button', { name: /Sửa đơn/ }));
  const dialog = screen.getByRole('dialog');
  const prices = within(dialog).getAllByLabelText('Giá Việt / món (VND)');
  expect(prices[0]).toHaveValue(null);
  fireEvent.change(prices[0], { target: { value: '100000' } });
  expect(within(dialog).getByText(/^Tổng đơn sau giảm/)).toHaveTextContent('Chưa đủ giá Việt');
  fireEvent.change(prices[1], { target: { value: '50000' } });
  fireEvent.change(within(dialog).getByLabelText('Giảm giá đơn (VND)'), { target: { value: String(discountAmount) } });
  const total = new Intl.NumberFormat('vi-VN').format(400000 - discountAmount);
  expect(within(dialog).getByText(/^Tổng đơn sau giảm/)).toHaveTextContent(total);
  const saved = { ...order, discountAmount, subtotalVnd: '400000', totalVnd: String(400000 - discountAmount),
    items: order.items.map((row, index) => ({ ...row, unitPriceVnd: index === 0 ? 100000 : 50000 })) };
  vi.mocked(api).mockResolvedValueOnce(saved);
  fireEvent.submit(within(dialog).getByRole('button', { name: 'Lưu đơn khách' }).closest('form')!);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(api).toHaveBeenLastCalledWith('gathering-orders/1-0/', 'PUT', expect.objectContaining({
    discountAmount, items: [expect.objectContaining({ unitPriceVnd: 100000 }), expect.objectContaining({ unitPriceVnd: 50000 })],
  }));
  expect(screen.getByText(/^Tổng đơn sau giảm/)).toHaveTextContent(total);
  fireEvent.click(screen.getByRole('button', { name: /Sửa đơn/ }));
  expect(within(screen.getByRole('dialog')).getAllByLabelText('Giá Việt / món (VND)')[0]).toHaveValue(100000);
  expect(within(screen.getByRole('dialog')).getByLabelText('Giảm giá đơn (VND)')).toHaveValue(discountAmount || null);
});

it('rejects discounts above the VND subtotal before saving', async () => {
  const batch = gathering(1, 'Gom tháng 11', ['Khách An']);
  batch.orders[0].items[0].unitPriceVnd = 100000;
  vi.mocked(api).mockResolvedValueOnce({ items: [batch] });
  render(<ProductManagement />);
  await screen.findByRole('heading', { name: 'Khách An' });
  fireEvent.click(screen.getByRole('button', { name: /Sửa đơn/ }));
  const dialog = screen.getByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('Giảm giá đơn (VND)'), { target: { value: '300001' } });
  fireEvent.submit(within(dialog).getByRole('button', { name: 'Lưu đơn khách' }).closest('form')!);
  expect(within(dialog).getByRole('alert')).toHaveTextContent('Giảm giá không được vượt quá tổng tiền hàng VND.');
  expect(api).toHaveBeenCalledTimes(1);
});

it('combines gathering and customer searches and keeps the customer filter when switching folders', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [
    gathering(1, 'Gom mùa đông A', ['Nguyễn An', 'Khách Bình']),
    gathering(2, 'Gom mùa hè', ['Nguyễn An']),
    gathering(3, 'Gom mùa đông B', ['Nguyễn An', 'Khách Chi']),
    gathering(4, 'Gom phụ kiện', ['Khách Bình']),
  ] });
  render(<ProductManagement />);
  await screen.findByRole('heading', { name: 'Nguyễn An' });
  fireEvent.change(screen.getByLabelText('Tìm kiếm khách hàng'), { target: { value: '  NGUYEN AN  ' } });
  const sidebar = within(screen.getByRole('complementary', { name: 'Các đợt gom' }));
  expect(sidebar.queryByRole('button', { name: /Gom phụ kiện/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Khách Bình' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Tìm kiếm đợt gom'), { target: { value: 'mua dong' } });
  expect(sidebar.getAllByRole('button', { name: /^Gom mùa đông/ })).toHaveLength(2);
  expect(sidebar.queryByRole('button', { name: /Gom mùa hè/ })).not.toBeInTheDocument();
  fireEvent.click(sidebar.getByRole('button', { name: /Gom mùa đông B/ }));
  expect(screen.getByLabelText('Tìm kiếm khách hàng')).toHaveValue('  NGUYEN AN  ');
  expect(screen.getByRole('heading', { name: 'Gom mùa đông B' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Nguyễn An' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Khách Chi' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Tìm kiếm khách hàng'), { target: { value: 'không tồn tại' } });
  expect(sidebar.queryByRole('button', { name: /^Gom/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Nguyễn An' })).not.toBeInTheDocument();
  expect(screen.getByText(/Không tìm thấy đợt gom hoặc khách hàng phù hợp/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Xóa tìm kiếm' }));
  expect(screen.getByLabelText('Tìm kiếm đợt gom')).toHaveValue('');
  expect(screen.getByLabelText('Tìm kiếm khách hàng')).toHaveValue('');
  expect(screen.getByRole('heading', { name: 'Khách Bình' })).toBeInTheDocument();
});

it('shows four gatherings at a time and resets pagination when searching', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: Array.from({ length: 9 }, (_, index) => gathering(index + 1, `Đợt gom ${index + 1}`, [`Khách ${index + 1}`])) });
  render(<ProductManagement />);
  await screen.findByRole('heading', { name: 'Khách 1' });
  const sidebar = within(screen.getByRole('complementary', { name: 'Các đợt gom' }));
  expect(sidebar.getAllByRole('button', { name: /^Đợt gom / })).toHaveLength(4);
  expect(sidebar.getByRole('button', { name: 'Xem 4 đợt gom trước' })).toBeDisabled();
  expect(sidebar.queryByRole('button', { name: /^Đợt gom 5 / })).not.toBeInTheDocument();
  fireEvent.click(sidebar.getByRole('button', { name: 'Xem 4 đợt gom tiếp theo' }));
  expect(sidebar.getAllByRole('button', { name: /^Đợt gom / })).toHaveLength(4);
  expect(screen.getByRole('heading', { name: 'Khách 5' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Khách 1' })).not.toBeInTheDocument();
  fireEvent.click(sidebar.getByRole('button', { name: 'Xem 4 đợt gom tiếp theo' }));
  expect(sidebar.getAllByRole('button', { name: /^Đợt gom / })).toHaveLength(1);
  expect(sidebar.getByRole('button', { name: 'Xem 4 đợt gom tiếp theo' })).toBeDisabled();
  expect(screen.getByRole('heading', { name: 'Khách 9' })).toBeInTheDocument();
  fireEvent.click(sidebar.getByRole('button', { name: 'Xem 4 đợt gom trước' }));
  expect(screen.getByRole('heading', { name: 'Khách 5' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Tìm kiếm đợt gom'), { target: { value: 'Đợt gom 2' } });
  expect(sidebar.getAllByRole('button', { name: /^Đợt gom / })).toHaveLength(1);
  expect(sidebar.getByRole('button', { name: 'Xem 4 đợt gom trước' })).toBeDisabled();
  expect(screen.getByRole('heading', { name: 'Khách 2' })).toBeInTheDocument();
  expect(sidebar.getByRole('status')).toHaveTextContent('Đang hiển thị 1–1 / 1 đợt gom');
});
