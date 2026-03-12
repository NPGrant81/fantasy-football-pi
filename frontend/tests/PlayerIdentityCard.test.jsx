import { render, screen } from '@testing-library/react';
import PlayerIdentityCard from '../src/components/player/PlayerIdentityCard';

describe('PlayerIdentityCard', () => {
  test('renders DEF team logo when team logo URL is provided', () => {
    render(
      <PlayerIdentityCard
        playerName="BUF Defense"
        position="DEF"
        nflTeam="BUF"
        teamLogoUrl="https://a.espncdn.com/i/teamlogos/nfl/500/buf.png"
      />
    );

    expect(screen.getByAltText('BUF Defense logo')).toBeInTheDocument();
  });

  test('does not render defense logo for non-DEF players without headshot', () => {
    render(
      <PlayerIdentityCard
        playerName="Patrick Mahomes"
        position="QB"
        nflTeam="KC"
      />
    );

    expect(screen.queryByAltText('KC Defense logo')).not.toBeInTheDocument();
    expect(screen.queryByAltText('Patrick Mahomes headshot')).not.toBeInTheDocument();
  });
});
