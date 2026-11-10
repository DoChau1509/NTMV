import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import OrderPayments from '../components/OrderPayments';
import { api } from '../lib/order-api';
import { Shipment } from '../lib/shop';

vi.mock('../lib/order-api', () => ({ api: vi.fn() }));
it('records a receipt and updates the order balance', async () => {
  const item: Shipment = { id: '1', code: 'CN1', trackingCode: '', name: 'Hàng', status: 0, note: '', updatedAt: '', totalDue: 385000, paidAmount: 0, balance: 385000, surcharge: 10000 };
  const saved = { ...item, paidAmount: 100000, balance: 285000, paymentCount: 1 };
  vi.mocked(api).mockResolvedValueOnce({ shipment: item, items: [] }).mockResolvedValueOnce({ shipment: saved, items: [{ id: '1', kind: 'receipt', amount: 100000, paidAt: new Date().toISOString(), note: 'Cọc lần 1', actor: 'Admin' }] });
  const onSaved = vi.fn();
  render(<OrderPayments item={item} onSaved={onSaved} />);
  const button = screen.getByRole('button', { name: 'Ghi thanh toán' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Số tiền (VNĐ)'), { target: { value: '100000' } });
  fireEvent.change(screen.getByLabelText('Ghi chú / mã giao dịch'), { target: { value: 'Cọc lần 1' } });
  fireEvent.click(button);
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
  expect(screen.getByText('Cọc lần 1')).toBeInTheDocument();
  expect(screen.getByText(/285.000/)).toBeInTheDocument();
});
