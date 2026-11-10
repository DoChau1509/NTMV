import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import OrderManagement from '../pages/OrderManagement';
import { api, downloadOrderFile } from '../lib/order-api';

vi.mock('../lib/order-api', () => ({ api: vi.fn(), downloadOrderFile: vi.fn() }));

it('exports the selected filters and backs up all orders independently of the filters', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [] });
  vi.mocked(downloadOrderFile).mockResolvedValue(undefined);
  render(<OrderManagement onChange={() => {}} />);
  const exportButton = screen.getByRole('button', { name: 'Xuất Excel theo bộ lọc' });
  await waitFor(() => expect(exportButton).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Tháng'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Năm'), { target: { value: '2026' } });
  fireEvent.change(screen.getByLabelText('Tìm bản ghi'), { target: { value: 'Nguyễn An' } });
  fireEvent.click(exportButton);
  await waitFor(() => expect(downloadOrderFile).toHaveBeenCalledTimes(1));
  const path = vi.mocked(downloadOrderFile).mock.calls[0][0];
  const params = new URL(path, 'https://example.com').searchParams;
  expect(params.get('year')).toBe('2026');
  expect(params.get('month')).toBe('10');
  expect(params.get('q')).toBe('Nguyễn An');
  const backup = screen.getByRole('button', { name: 'Sao lưu toàn bộ (.xlsx)' });
  await waitFor(() => expect(backup).toBeEnabled());
  fireEvent.click(backup);
  await waitFor(() => expect(downloadOrderFile).toHaveBeenLastCalledWith('shipments/export/?backup=1'));
});

it('shows the download error without claiming a successful backup', async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [] });
  vi.mocked(downloadOrderFile).mockRejectedValueOnce(new Error('Không thể tải file Excel.'));
  render(<OrderManagement onChange={() => {}} />);
  const backup = screen.getByRole('button', { name: 'Sao lưu toàn bộ (.xlsx)' });
  await waitFor(() => expect(backup).toBeEnabled());
  fireEvent.click(backup);
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải file Excel.');
});
