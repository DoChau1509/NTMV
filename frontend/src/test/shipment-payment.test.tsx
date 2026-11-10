import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import ShipmentPayment from '../components/ShipmentPayment';
import { money, Shipment } from '../lib/shop';

afterEach(cleanup);
const item: Shipment = { id: '1', code: 'CN1', trackingCode: '', name: 'Hàng', status: 0, note: '', updatedAt: '' };

it.each(['deposit', 'domestic_shipping'] as const)('shows the remaining VND amount for %s', (paymentStatus) => {
  render(<ShipmentPayment item={{ ...item, paymentStatus, remainingAmount: 125000 }} />);
  expect(screen.getByText(money(125000), { normalizer: (text) => text })).toBeInTheDocument();
  expect(screen.getByText(paymentStatus === 'deposit' ? 'Cọc' : 'Còn phụ phí')).toBeInTheDocument();
});

it('shows paid orders without an outstanding balance', () => {
  render(<ShipmentPayment item={{ ...item, paymentStatus: 'paid' }} />);
  expect(screen.getByText('Thanh toán đủ')).toBeInTheDocument();
  expect(screen.queryByText(/Còn lại/)).not.toBeInTheDocument();
});

it('does not mark old orders as paid', () => {
  render(<ShipmentPayment item={item} />);
  expect(screen.getByText('Chưa cập nhật')).toBeInTheDocument();
});
