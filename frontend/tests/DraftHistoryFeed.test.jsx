import { render, screen } from '@testing-library/react';
import React from 'react';
import DraftHistoryFeed from '../src/components/draft/DraftHistoryFeed';

// simple feed item
const sampleOwners = [{ id: 1, username: 'statsgeek' }];
const sampleHistory = [
  { id: 101, owner_id: 1, player_name: 'John Doe', position: 'RB', amount: 15, timestamp: '2025-01-01T00:00:00Z' },
];

describe('DraftHistoryFeed', () => {
  it('renders player name along with owner and amount', () => {
    render(<DraftHistoryFeed history={sampleHistory} owners={sampleOwners} />);
    expect(screen.getByText('statsgeek')).toBeInTheDocument();
    expect(screen.getByText(/John Doe/i)).toBeInTheDocument();
    expect(screen.getByText(/\$15/)).toBeInTheDocument();
  });
});
