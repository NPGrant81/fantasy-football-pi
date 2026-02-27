import { render, screen, fireEvent } from '@testing-library/react';
import AdminSettings from '../src/components/admin/AdminSettings';

describe('AdminSettings tabs', () => {
  test('renders tab buttons and switches content', () => {
    render(<AdminSettings />);
    const scoringTab = screen.getByRole('button', { name: /Scoring Rules/i });
    const dataTab = screen.getByRole('button', { name: /Data Management/i });
    expect(scoringTab).toBeInTheDocument();
    expect(dataTab).toBeInTheDocument();

    // scoring content initially visible
    expect(screen.getByText(/Passing/i)).toBeInTheDocument();
    // switch to data tab
    fireEvent.click(dataTab);
    expect(screen.getByText(/NFL Data Refresh/i)).toBeInTheDocument();
  });
});
