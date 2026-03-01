import { render, screen, fireEvent } from '@testing-library/react';
import BestAvailableList from '../src/components/draft/BestAvailableList';

const sample = [
  { id: 1, rank: 1, name: 'Alice', pos: 'QB', projectedValue: 10 },
  { id: 2, rank: 2, name: 'Bob', pos: 'RB', projectedValue: 20 },
  { id: 3, rank: 3, name: 'Cara', pos: 'WR', projectedValue: 15 },
];

describe('BestAvailableList component', () => {
  test('renders table headers and rows', () => {
    render(<BestAvailableList players={sample} open={true} />);
    expect(screen.getByText(/Rank/i)).toBeInTheDocument();
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
  });

  test('filter buttons affect row visibility', () => {
    render(<BestAvailableList players={sample} open={true} />);
    const rbBtn = screen.getByRole('button', { name: 'RB' });
    fireEvent.click(rbBtn);
    expect(screen.queryByText('Alice')).toBeNull();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  test('sort toggles on header click', () => {
    render(<BestAvailableList players={sample} open={true} />);
    const playerHeader = screen.getByText('Player');
    fireEvent.click(playerHeader);
    // sorted ascending by name: Alice, Bob, Cara - initial order already this
    fireEvent.click(playerHeader);
    // descending now, top row should contain Cara
    const firstCell = screen.getAllByRole('cell')[0];
    expect(firstCell.textContent).toContain('3');
  });

  test('collapsing hides the full list', () => {
    const { rerender } = render(<BestAvailableList players={sample} open={true} />);
    expect(screen.getByText('Best Available')).toBeInTheDocument();
    rerender(<BestAvailableList players={sample} open={false} onToggle={() => {}} />);
    expect(screen.queryByText('Best Available')).toBeNull();
    expect(screen.getByText(/Show Best Available/i)).toBeInTheDocument();
  });
});