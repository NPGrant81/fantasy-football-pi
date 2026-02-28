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
import { POSITION_COLORS } from '../src/constants/ui';

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
    expect(emptyCell).toHaveClass('h-20');

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

  it('displays drafted player info inside cell', () => {
    const teams2 = [{ id: 3, name: 'CellTest', remainingBudget: 50 }];
    const history2 = [
      { owner_id: 3, player_name: 'Travis Kelce', position: 'TE', amount: 20 },
    ];
    render(
      <DraftBoardGrid teams={teams2} history={history2} rosterLimit={1} />
    );

    // name should wrap or at least be present in DOM
    const nameEl = screen.getByText('Travis Kelce');
    expect(nameEl).toBeInTheDocument();
    expect(nameEl).toHaveClass('break-words');

    // price should display on its own line, position removed
    expect(screen.getByText(/\$?\s*20/)).toBeInTheDocument();
    // drafted cell background should be gold for any player
    const cell = nameEl.closest('div'); // the immediate div is the cell
    // background should correspond to the player's position color
    expect(cell).toHaveClass(POSITION_COLORS.TE);
    // cell should also have a muted slate outline border
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
    // count divs that received the highlighted class
    const highlighted = container.querySelectorAll('div');
    // two cells should have position-color backgrounds
    const colored = Array.from(highlighted).filter((d) =>
      Object.values(POSITION_COLORS).some((cls) => d.classList.contains(cls))
    );
    expect(colored.length).toBe(2);
    colored.forEach((c) => {
      expect(
        Object.values(POSITION_COLORS).some((cls) => c.classList.contains(cls))
      ).toBe(true);
      expect(c.classList.contains('border-slate-600')).toBe(true);
    });
  });
});

// additional layout test for auction block width
import AuctionBlock from '../src/components/draft/AuctionBlock';

describe('AuctionBlock layout', () => {
  it('constrains itself to a reasonable max width', () => {
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
    expect(wrapper).toHaveClass('max-w-[240px]');
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

  it('defines correct grid column spans for board and sidebar', () => {
    const { container } = render(
      <DraftBoard
        token={null}
        activeOwnerId={1}
        activeLeagueId={1}
        setSubHeader={() => {}}
      />
    );
    const aside = container.querySelector('aside');
    expect(aside).toHaveClass('md:col-span-3');
    const section = container.querySelector('section');
    // when sidebar hidden initial state, section spans full width
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
    // there are actually two buttons containing the phrase "Show Best";
    // pick the simple toggle (without the "Available ▶" suffix)
    const toggleCandidates = screen.getAllByText(/Show Best/i);
    const toggle = toggleCandidates.find((btn) => btn.textContent === 'Show Best');
    expect(toggle).toBeDefined();
    fireEvent.click(toggle);
    const aside = container.querySelector('aside');
    expect(aside).not.toHaveClass('hidden');
  });
});
