import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import QuickSharedFee from '../components/QuickSharedFee';
import { Shipment } from '../lib/shop';

it('edits the shared fee and lets the user cancel a draft', () => {
  const onSave = vi.fn();
  const item: Shipment = { id: '1', code: 'CN123', trackingCode: '', name: 'Hàng', status: 0, note: '', updatedAt: '', sharedFee: 5000 };
  render(<QuickSharedFee item={item} onSave={onSave} />);
  fireEvent.click(screen.getByRole('button', { name: 'Sửa công chia CN123' }));
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '8000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Hủy' }));
  expect(onSave).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Sửa công chia CN123' }));
  expect(screen.getByRole('spinbutton')).toHaveValue(5000);
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '8000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));
  expect(onSave).toHaveBeenCalledWith({ sharedFee: 8000 });
});
