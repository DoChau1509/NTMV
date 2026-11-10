import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import QuickPayment from '../components/QuickPayment';
import { extractProductUrl, Shipment } from '../lib/shop';

afterEach(cleanup);
const item: Shipment = { id: '1', code: 'CN1', trackingCode: '', name: 'Hàng', status: 0, paymentStatus: 'paid', note: '', updatedAt: '' };

it('extracts the URL from a shared product message and preserves its query', () => {
  expect(extractProductUrl('【闲鱼】https://m.tb.cn/h.8B7e93e?tk=2D83TK0Rmbt HU293 「快来捡漏【商品】」\n点击链接直接打开')).toBe('https://m.tb.cn/h.8B7e93e?tk=2D83TK0Rmbt');
});

it('saves payment and remaining amount together without leaving the list', () => {
  const onSave = vi.fn();
  render(<QuickPayment item={item} onSave={onSave} />);
  fireEvent.change(screen.getByLabelText('Thanh toán CN1'), { target: { value: 'deposit' } });
  expect(onSave).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Số tiền còn lại CN1'), { target: { value: '125000' } });
  fireEvent.click(screen.getByText('Lưu'));
  expect(onSave).toHaveBeenCalledWith({ paymentStatus: 'deposit', remainingAmount: 125000 });
});

it('cancels a payment change', () => {
  const onSave = vi.fn();
  render(<QuickPayment item={item} onSave={onSave} />);
  fireEvent.change(screen.getByLabelText('Thanh toán CN1'), { target: { value: 'deposit' } });
  fireEvent.click(screen.getByText('Hủy'));
  expect(screen.getByLabelText('Thanh toán CN1')).toHaveValue('paid');
  expect(screen.queryByText('Lưu')).toBeNull();
  expect(onSave).not.toHaveBeenCalled();
});
