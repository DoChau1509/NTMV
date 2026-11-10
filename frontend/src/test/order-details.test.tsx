import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import OrderManagement from '../pages/OrderManagement';
import { api } from '../lib/order-api';

vi.mock('../lib/order-api', () => ({ api: vi.fn() }));

it('opens order details with the surcharge breakdown and calculated balance', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [{
    id: '1', code: 'CN1', trackingCode: 'YD1', name: 'Hàng', buyerName: 'An', status: 3,
    note: '', updatedAt: new Date().toISOString(), cnyPrice: '10.01', lockedRate: 3600.1,
    baseAmount: 36038, laborFee: 15000, weightFeeTotal: 22000, domesticFeeTotal: 8000,
    otherFeeTotal: 5000, surchargeTotal: 35000, totalDue: 86038, paidAmount: 51038,
    balance: 35000, remainingAmount: 35000, paymentStatus: 'domestic_shipping', paymentCount: 4,
  }] });
  render(<OrderManagement onChange={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Chi tiết CN1' }));
  const dialog = screen.getByRole('dialog', { name: 'Chi tiết đơn · CN1' });
  expect(within(dialog).getByText('Phí cân').parentElement?.textContent).toContain('22.000');
  expect(within(dialog).getByText('Phí nội địa').parentElement?.textContent).toContain('8.000');
  expect(within(dialog).getByText('Phí khác / chưa phân loại').parentElement?.textContent).toContain('5.000');
  expect(within(dialog).getByText('Còn cần thanh toán').parentElement?.textContent).toContain('35.000');
  expect(within(dialog).getByText(/Trạng thái thanh toán: Còn phụ phí/)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Đóng chi tiết' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it('allows selecting payment status in the table and in the edit form', async () => {
  const item = { id: '2', code: 'CN2', trackingCode: '', name: 'Hàng', status: 0, note: '', updatedAt: new Date().toISOString(), totalDue: 57000, paidAmount: 210, balance: 56790, remainingAmount: 57000, paymentCount: 1, paymentStatus: 'deposit', paymentStatusOverride: null };
  vi.mocked(api).mockResolvedValueOnce({ items: [item] })
    .mockResolvedValueOnce({ ...item, paymentStatus: 'paid', paymentStatusOverride: 'paid' })
    .mockResolvedValueOnce({ ...item, paymentStatus: 'domestic_shipping', paymentStatusOverride: 'domestic_shipping' });
  render(<OrderManagement onChange={() => {}} />);
  const select = await screen.findByLabelText('Thanh toán CN2');
  await waitFor(() => expect(select).toBeEnabled());
  fireEvent.change(select, { target: { value: 'paid' } });
  await waitFor(() => expect(select).toHaveValue('paid'));
  expect(vi.mocked(api)).toHaveBeenCalledWith('shipments/2/', 'PATCH', { paymentStatusOverride: 'paid' });
  fireEvent.click(screen.getByRole('button', { name: 'Sửa CN2' }));
  const editSelect = screen.getByLabelText('Trạng thái thanh toán');
  expect(editSelect).toBeEnabled();
  fireEvent.change(editSelect, { target: { value: 'domestic_shipping' } });
  fireEvent.click(screen.getByRole('button', { name: /Lưu trạng thái/ }));
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith('shipments/2/', 'PUT', expect.objectContaining({ paymentStatusOverride: 'domestic_shipping' })));
});
