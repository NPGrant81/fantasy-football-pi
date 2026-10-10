import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import CommishAdmin from '../src/pages/commissioner/CommishAdmin';

const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }));
vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
}));

describe('Commissioner controls', () => {
  test('renders management actions and navigates to scoring rules', () => {
    render(<CommishAdmin />);
    const scoring = screen.getByRole('button', { name: /Manage Scoring Rules/i });
    expect(screen.getByRole('button', { name: /Manage Owners/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Edit Waiver Rules/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Manage Trades/i })).toBeInTheDocument();
    fireEvent.click(scoring);
    expect(navigate).toHaveBeenCalledWith('/commissioner/manage-scoring-rules');
  });
});
