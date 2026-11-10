import { render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import OrderHistory from '../components/OrderHistory';
import OrderManagement from '../pages/OrderManagement';
import { api } from '../lib/order-api';
import { defaultSettings } from '../lib/shop';

vi.mock('../lib/order-api', () => ({ api: vi.fn() }));

it('shows the actor, timestamp and before/after values', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [{ id: '1', actor: 'Admin (boss)', action: 'update', createdAt: '2026-11-05T10:00:00Z', changes: { status: { before: 0, after: 2 }, laborFee: { before: 10000, after: 15000 } } }] });
  render(<OrderHistory id="1" code="CN123" version="1" />);
  expect(await screen.findByText(/Admin \(boss\)/)).toBeInTheDocument();
  expect(screen.getByText(/Đã mua → Kho Trung/)).toBeInTheDocument();
  expect(screen.getByText(/10.000.*→.*15.000/)).toBeInTheDocument();
});

it('uses saved fees in the table and total after the global pricing changes', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [{ id: '1', code: 'CN123', trackingCode: '', name: 'Hàng', status: 0, note: '', updatedAt: new Date().toISOString(), cnyPrice: '100', sharedFee: 1000, laborFee: 9000, lockedRate: 3600, pricingSnapshot: { rate: 3600, tiers: [{ from: 0, type: 'percent', value: 2.5 }] } }] });
  render(<OrderManagement settings={{ ...defaultSettings, rate: 5000 }} onChange={() => {}} />);
  await screen.findByText('CN123');
  const summary = screen.getByRole('status', { name: 'Tổng thực nhận theo bộ lọc' });
  expect(within(summary).getByTestId('orders-net-total').textContent).toContain('8.000');
});
