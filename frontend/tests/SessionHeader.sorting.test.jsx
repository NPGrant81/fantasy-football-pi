import { render, screen, fireEvent } from '@testing-library/react';
import SessionHeader from '../src/components/draft/SessionHeader';
import { DRAFT_BOARD_SORT_MODE } from '../src/utils/draftBoardSort';

describe('SessionHeader sort control', () => {
  test('renders sort dropdown in header and emits mode changes', () => {
    const onSortModeChange = vi.fn();

    render(
      <SessionHeader
        sessionId="LEAGUE_1_YEAR_2026"
        rosterSize={16}
        leagueName="League 1"
        isCommissioner={false}
        isPaused={false}
        sortMode={DRAFT_BOARD_SORT_MODE.DRAFT_ORDER}
        onSortModeChange={onSortModeChange}
      />
    );

    const select = screen.getByLabelText(/sort team column/i);
    expect(select).toBeInTheDocument();

    fireEvent.change(select, {
      target: { value: DRAFT_BOARD_SORT_MODE.VALUE_DESC },
    });

    expect(onSortModeChange).toHaveBeenCalledWith(
      DRAFT_BOARD_SORT_MODE.VALUE_DESC
    );
  });
});
