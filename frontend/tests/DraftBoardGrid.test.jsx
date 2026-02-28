import { render, screen } from '@testing-library/react';
import React from 'react';
import DraftBoardGrid from '../src/components/draft/DraftBoardGrid';

// simple fixtures
// include alternate keys that come from API (team_name, username)
const teams = [
  { id: 1, team_name: 'War Alpha', remainingBudget: 187 },
];
const history = [
  { owner_id: 1, player_name: 'Player A', position: 'QB', amount: 3 },
];

describe('DraftBoardGrid header', () => {
  it('displays team name (using team_name key) and labeled stats', () => {
    render(<DraftBoardGrid teams={teams} history={history} rosterLimit={2} />);

    const nameEl = screen.getByText('War Alpha');
    expect(nameEl).toBeInTheDocument();
    expect(nameEl).toHaveClass('break-words');
    // stats line should contain "Drafted" and "Remaining" text
    const statsEl = screen.getByText(/1 Drafted/);
    expect(statsEl).toBeInTheDocument();
    expect(statsEl).toHaveClass('text-green-400');
    expect(screen.getByText(/\$187 Remaining/)).toBeInTheDocument();
  });

  it('renders zeros correctly with labels', () => {
    render(
      <DraftBoardGrid teams={[{ id: 2, name: 'Empty', remainingBudget: 0 }]} history={[]} rosterLimit={1} />
    );
    expect(screen.getByText('Empty')).toBeInTheDocument();
    expect(screen.getByText(/0 Drafted/)).toBeInTheDocument();
    expect(screen.getByText(/\$0 Remaining/)).toBeInTheDocument();
  });

  it('displays drafted player info inside cell', () => {
    const teams2 = [{ id: 3, name: 'CellTest', remainingBudget: 50 }];
    const history2 = [
      { owner_id: 3, player_name: 'Travis Kelce', position: 'TE', amount: 20 },
    ];
    render(<DraftBoardGrid teams={teams2} history={history2} rosterLimit={1} />);

    // name should wrap or at least be present in DOM
    const nameEl = screen.getByText('Travis Kelce');
    expect(nameEl).toBeInTheDocument();
    expect(nameEl).toHaveClass('break-words');

    expect(screen.getByText(/TE\s*\|\s*\$?\s*20\s*Drafted/)).toBeInTheDocument();
  });
});
