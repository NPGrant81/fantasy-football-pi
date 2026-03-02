import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { vi } from 'vitest';
// ensure VITE_API_BASE_URL exists to keep apiClient happy during tests
// avoid assigning to import.meta.env directly (read-only), just set the property if missing
if (!import.meta?.env) {
  // some test runners may not initialize import.meta.env, so define it safely
  Object.defineProperty(import.meta, 'env', { value: {} });
}
if (!('VITE_API_BASE_URL' in import.meta.env)) {
  import.meta.env.VITE_API_BASE_URL = '';
}
import DraftBoardGrid from '../src/components/draft/DraftBoardGrid';

// simple fixtures
// include alternate keys that come from API (team_name, username)
const teams = [{ id: 1, team_name: 'War Alpha', remainingBudget: 187 }];
const history = [
  { owner_id: 1, player_name: 'Player A', position: 'QB', amount: 3 },
];

describe('DraftBoardGrid header', () => {
  it('displays team name (using team_name key) and labeled stats', () => {
    render(<DraftBoardGrid teams={teams} history={history} rosterLimit={2} />);

    // top-level flex container should use the tighter gap
    const gridContainer = screen.getByTestId('draft-board');
    expect(gridContainer).toHaveClass('gap-1');

    const nameEl = screen.getByText('War Alpha');
    expect(nameEl).toBeInTheDocument();
    expect(nameEl).toHaveClass('break-words');
    // header container should enforce fixed height and vertical spacing
    const headerDiv = nameEl.closest('div');
    expect(headerDiv).toHaveClass('h-24', 'justify-between');
    // and the column itself should flex to fill available space
    const columnDiv = headerDiv.parentElement;
    expect(columnDiv).toHaveClass('flex-1');

    // ensure empty cells are tall enough for two-line names
    const emptyCell = screen.getAllByText('OPEN')[0].closest('div');
    expect(emptyCell).toHaveClass('h-24');

    // stats line should contain count and remaining budget
    const statsEl = screen.getByText(/1 \|/);
    expect(statsEl).toBeInTheDocument();
    expect(statsEl).toHaveClass('text-green-400');
    expect(screen.getByText(/\$187 Remaining/)).toBeInTheDocument();
  });

  it('renders zeros correctly with labels', () => {
    render(
      <DraftBoardGrid
        teams={[{ id: 2, name: 'Empty', remainingBudget: 0 }]}
        history={[]}
        rosterLimit={1}
      />
    );
    expect(screen.getByText('Empty')).toBeInTheDocument();
    // header now shows count followed by pipe character rather than the word "Drafted"
    expect(screen.getByText(/0 \|/)).toBeInTheDocument();
    expect(screen.getByText(/\$0 Remaining/)).toBeInTheDocument();
  });

  it('displays drafted player info inside cell with new layout', () => {
    const teams2 = [{ id: 3, name: 'CellTest', remainingBudget: 50 }];
    const history2 = [
      { owner_id: 3, player_name: 'Travis Kelce', position: 'TE', amount: 20 },
    ];
    render(
      <DraftBoardGrid teams={teams2} history={history2} rosterLimit={1} />
    );

    // first name should appear separately and cost right-aligned
    expect(screen.getByText('Travis')).toBeInTheDocument();
    expect(screen.getByText('$20')).toBeInTheDocument();
    // last name should appear large and uppercase
    const lastEl = screen.getByText('KELCE');
    expect(lastEl).toBeInTheDocument();
    expect(lastEl).toHaveClass('uppercase');
    // ensure there is no position text anywhere
    expect(screen.queryByText(/TE/)).toBeNull();

    // drafted cell should have a position color class and drafted border treatment
    const cell = screen.getByTestId('player-card');
    expect(cell.className).toMatch(/bg-/);
    expect(cell).toHaveClass('border-2', 'border-slate-600');
  });

  it('highlights every drafted slot when multiple picks exist', () => {
    const teams3 = [{ id: 4, name: 'Multi', remainingBudget: 100 }];
    const history3 = [
      { owner_id: 4, player_name: 'A', position: 'QB', amount: 10 },
      { owner_id: 4, player_name: 'B', position: 'RB', amount: 15 },
    ];
    const { container } = render(
      <DraftBoardGrid teams={teams3} history={history3} rosterLimit={3} />
    );
    // each drafted player should render as a highlighted player card
    const draftedCards = container.querySelectorAll('[data-testid="player-card"]');
    expect(draftedCards.length).toBe(2);
    draftedCards.forEach((card) => {
      expect(card.className).toMatch(/bg-/);
      expect(card.classList.contains('border-slate-600')).toBe(true);
    });
  });
});

// additional layout test for auction block width
import AuctionBlock from '../src/components/draft/AuctionBlock';

describe('AuctionBlock layout', () => {
  it('expands to full width under its parent', () => {
    const { container } = render(
      <AuctionBlock
        playerName=""
        handleSearchChange={() => {}}
        suggestions={[]}
        showSuggestions={false}
        posFilter="ALL"
        setPosFilter={() => {}}
        winnerId={null}
        setWinnerId={() => {}}
        owners={[]}
        activeStats={null}
        bidAmount={1}
        setBidAmount={() => {}}
        handleDraft={() => {}}
        timeLeft={0}
        isTimerRunning={false}
        reset={() => {}}
        start={() => {}}
        nominatorId={null}
        isCommissioner={false}
      />
    );
    const wrapper = container.firstChild;
    // root container should now be full width and flexible
    expect(wrapper).toHaveClass('w-full');
  });

  it('leftOnly mode shows nominator, search input, and pos filters', () => {
    const { getByPlaceholderText, getByText } = render(
      <AuctionBlock
        leftOnly
        playerName=""
        handleSearchChange={() => {}}
        suggestions={[]}
        showSuggestions={false}
        posFilter="ALL"
        setPosFilter={() => {}}
        winnerId={null}
        setWinnerId={() => {}}
        owners={[]}
        activeStats={null}
        bidAmount={1}
        setBidAmount={() => {}}
        handleDraft={() => {}}
        timeLeft={0}
        isTimerRunning={false}
        reset={() => {}}
        start={() => {}}
        nominatorId={null}
        isCommissioner={false}
      />
    );
    expect(getByPlaceholderText(/Nominate Player/i)).toBeInTheDocument();
    expect(getByText(/Nominator/i)).toBeInTheDocument();
    expect(getByText(/ALL/i)).toBeInTheDocument();
  });

  it('default/full mode shows full bidding interface with filters and buttons', () => {
    const { queryByPlaceholderText, getByText } = render(
      <AuctionBlock
        playerName=""
        handleSearchChange={() => {}}
        suggestions={[]}
        showSuggestions={false}
        posFilter="ALL"
        setPosFilter={() => {}}
        winnerId={null}
        setWinnerId={() => {}}
        owners={[]}
        activeStats={{ budget: 100, maxBid: 50 }}
        bidAmount={1}
        setBidAmount={() => {}}
        handleDraft={() => {}}
        timeLeft={0}
        isTimerRunning={false}
        reset={() => {}}
        start={() => {}}
        nominatorId={null}
        isCommissioner={false}
      />
    );
    // full mode should show the search input as well as bidding controls
    expect(queryByPlaceholderText(/Nominate Player/i)).toBeInTheDocument();
    expect(getByText(/Winning Bidder/i)).toBeInTheDocument();
  });

  it('top row flex container aligns items to bottom and integrates Show Best toggle', () => {
    const { getByText, getByTestId } = render(
      <AuctionBlock
        playerName=""
        handleSearchChange={() => {}}
        suggestions={[]}
        showSuggestions={false}
        posFilter="ALL"
        setPosFilter={() => {}}
        winnerId={null}
        setWinnerId={() => {}}
        owners={[]}
        activeStats={null}
        bidAmount={1}
        setBidAmount={() => {}}
        handleDraft={() => {}}
        timeLeft={0}
        isTimerRunning={false}
        reset={() => {}}
        start={() => {}}
        nominatorId={null}
        isCommissioner={false}
        showBestSidebar={false}
        toggleSidebar={() => {}}
      />
    );
    const topRow = getByTestId('auction-top-row');
    expect(topRow).toHaveClass('grid');
    // Show Best button should exist inside AuctionBlock
    expect(getByText(/Show Best/i)).toBeInTheDocument();

    // sold button should be present below
    expect(getByText(/SOLD/i)).toBeInTheDocument();
  });
});

// verify the page layout gives the sidebar two grid columns
// DraftBoard imports are deferred since the module pulls in api/client (which
// references import.meta.env) and static imports run before our env stub.

describe('DraftBoard page layout', () => {
  let DraftBoard;

  beforeEach(async () => {
    // ensure the environment variable exists before importing any modules that
    // read it. import.meta.env may be undefined until this point in some
    // test runners.
    if (!import.meta?.env) {
      Object.defineProperty(import.meta, 'env', { value: {} });
    }
    if (!('VITE_API_BASE_URL' in import.meta.env)) {
      import.meta.env.VITE_API_BASE_URL = '';
    }

    // stub budget call which would otherwise return undefined
    const orig = (await import('../src/api/client')).default;
    orig.get = vi.fn().mockResolvedValue({ data: [] });

    // now that the env is set and client is stubbed we can load the page
    DraftBoard = (await import('../src/pages/DraftBoard')).default;
  });

  it('renders board full-width and keeps best-available overlay hidden by default', () => {
    const { container } = render(
      <DraftBoard
        token={null}
        activeOwnerId={1}
        activeLeagueId={1}
        setSubHeader={() => {}}
      />
    );
    const aside = container.querySelector('aside');
    expect(aside).toBeNull();
    const section = container.querySelector('section');
    // board stays full width and no longer shrinks for a side column
    expect(section).toHaveClass('col-span-12');
  });

  it('sidebar toggle button shows/hides the list', () => {
    const { container } = render(
      <DraftBoard
        token={null}
        activeOwnerId={1}
        activeLeagueId={1}
        setSubHeader={() => {}}
      />
    );
    const toggle = screen.getByRole('button', { name: /show\s*best/i });
    fireEvent.click(toggle);
    const aside = container.querySelector('aside');
    expect(aside).toBeInTheDocument();
  });
});
