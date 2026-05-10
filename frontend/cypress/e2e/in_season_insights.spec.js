/**
 * E2E smoke test for the In-Season Weekly Insights panel on the /team page.
 * Issue #114 – verifies the panel renders waiver targets, start/sit, and alerts
 * when the backend returns a populated in-season-insights payload.
 */

describe('In-Season Insights panel', () => {
  const authUser = {
    user_id: 5,
    username: 'insights-e2e-user',
    is_commissioner: false,
    league_id: 1,
  };

  const insightsPayload = {
    roster_needs: [
      { position: 'RB', deficit: 1.2 },
      { position: 'TE', deficit: 0.7 },
    ],
    waiver_targets: [
      {
        player_id: 201,
        player_name: 'Rookie RB',
        position: 'RB',
        nfl_team: 'LAR',
        personalized_score: 7.4,
        recommended_faab_bid_pct: 18,
        breakout_probability: 0.42,
      },
      {
        player_id: 202,
        player_name: 'Slot WR',
        position: 'WR',
        nfl_team: 'DAL',
        personalized_score: 5.1,
        recommended_faab_bid_pct: 8,
        breakout_probability: 0.3,
      },
    ],
    start_sit_recommendations: [
      {
        player_id: 11,
        player_name: 'QB Starter',
        recommendation: 'start',
        explanation: 'Great matchup vs weak secondary.',
      },
      {
        player_id: 22,
        player_name: 'WR Bench',
        recommendation: 'consider_bench',
        explanation: 'Tough CB shadow this week.',
      },
    ],
    trade_leverage: [
      { position: 'QB', delta_vs_league: 1.5, recommended_action: 'sell_high' },
      { position: 'RB', delta_vs_league: -2.1, recommended_action: 'buy_help' },
    ],
    alerts: [
      { message: 'WR2 is questionable - monitor practice reports.', severity: 'medium' },
    ],
    meta: { owner_id: 5, season: 2026, week: 9 },
  };

  beforeEach(() => {
    cy.viewport(1366, 768);

    cy.intercept('GET', '**/advisor/status', { statusCode: 200, body: { enabled: false } });
    cy.intercept('POST', '**/analytics/visit', { statusCode: 200, body: { ok: true } });

    cy.intercept('GET', '**/auth/me*', { statusCode: 200, body: authUser }).as('authMe');

    cy.intercept('GET', '**/leagues/1', {
      statusCode: 200,
      body: { id: 1, name: 'Insights League', draft_status: 'POST_DRAFT' },
    }).as('league');

    cy.intercept('GET', '**/leagues/1/settings', {
      statusCode: 200,
      body: {
        draft_year: 2026,
        roster_size: 14,
        starting_slots: {
          MAX_QB: 1,
          MAX_RB: 3,
          MAX_WR: 3,
          MAX_TE: 2,
          MAX_DEF: 1,
          MAX_K: 1,
          MAX_FLEX: 1,
          ACTIVE_ROSTER_SIZE: 9,
        },
        scoring_rules: [],
        waiver_deadline: null,
        trade_deadline: null,
      },
    }).as('settings');

    cy.intercept('GET', '**/leagues/owners*', {
      statusCode: 200,
      body: [{ id: 5, username: 'insights-e2e-user', team_name: 'Insights Team' }],
    }).as('owners');

    cy.intercept('GET', '**/dashboard/5*', {
      statusCode: 200,
      body: { standing: 3, record: '5-3' },
    }).as('dashboard');

    cy.intercept('GET', '**/team/5*', {
      statusCode: 200,
      body: {
        team_name: 'Insights Team',
        lineup_submitted: false,
        players: [
          { player_id: 11, id: 11, name: 'QB Starter', position: 'QB', nfl_team: 'BUF', status: 'STARTER', projected_points: 22.5 },
          { player_id: 22, id: 22, name: 'WR Bench', position: 'WR', nfl_team: 'SF', status: 'BENCH', projected_points: 10.1 },
        ],
      },
    }).as('team');

    cy.intercept(
      'GET',
      '**/analytics/league/1/in-season-insights*',
      { statusCode: 200, body: insightsPayload },
    ).as('insights');

    cy.visit('/team', {
      onBeforeLoad(win) {
        win.localStorage.setItem('fantasyToken', 'e2e-token');
        win.localStorage.setItem('user_id', '5');
        win.localStorage.setItem('fantasyLeagueId', '1');
      },
    });

    cy.wait('@authMe');
    cy.wait('@team');
  });

  it('renders the Weekly Insights panel with waiver targets', () => {
    cy.wait('@insights');

    cy.get('[data-testid="weekly-insights-panel"]').should('exist');
    cy.contains('Weekly Insights').should('be.visible');
    cy.contains('Week 9').should('be.visible');

    // Waiver targets
    cy.contains('Top Waiver Targets').should('be.visible');
    cy.contains('Rookie RB').should('be.visible');
    cy.contains('Slot WR').should('be.visible');
  });

  it('shows start/sit recommendations', () => {
    cy.wait('@insights');

    cy.contains('Great matchup vs weak secondary.').should('be.visible');
    cy.contains('Tough CB shadow this week.').should('be.visible');
  });

  it('displays alerts', () => {
    cy.wait('@insights');

    cy.contains('WR2 is questionable').should('be.visible');
  });

  it('shows trade leverage deltas', () => {
    cy.wait('@insights');

    cy.contains('Trade Leverage').should('be.visible');
    cy.contains('QB').should('be.visible');
    cy.contains('+1.5').should('be.visible');
  });

  it('collapses and expands the panel', () => {
    cy.wait('@insights');

    // Panel is expanded by default — waiver targets visible
    cy.contains('Rookie RB').should('be.visible');

    // Click header to collapse
    cy.get('[data-testid="weekly-insights-panel"]').find('button').first().click();
    cy.contains('Rookie RB').should('not.exist');

    // Click again to expand
    cy.get('[data-testid="weekly-insights-panel"]').find('button').first().click();
    cy.contains('Rookie RB').should('be.visible');
  });
});
