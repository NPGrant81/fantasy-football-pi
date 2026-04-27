describe('DraftBoard smoke', () => {
  it('renders DraftBoard without runtime errors', () => {
    cy.intercept('GET', '**/advisor/status', {
      statusCode: 200,
      body: { enabled: false },
    }).as('advisorStatus');

    cy.intercept('GET', '**/auth/me', {
      statusCode: 200,
      body: {
        user_id: 5,
        username: 'e2e-user',
        is_commissioner: true,
        league_id: 1,
      },
    }).as('authMe');

    cy.intercept('GET', '**/leagues/owners?*', {
      statusCode: 200,
      body: [
        { id: 5, username: 'e2e-user', team_name: 'E2E Team' },
        { id: 6, username: 'other-user', team_name: 'Other Team' },
      ],
    }).as('owners');

    cy.intercept('GET', /\/players\//, {
      statusCode: 200,
      body: [
        {
          id: 1001,
          name: 'Justin Fields',
          position: 'QB',
          nfl_team: 'NYJ',
          rank: 1,
        },
      ],
    }).as('players');

    cy.intercept('GET', '**/draft/history?*', {
      statusCode: 200,
      body: [],
    }).as('history');

    cy.intercept('GET', '**/leagues/1', {
      statusCode: 200,
      body: {
        id: 1,
        name: 'E2E League',
        draft_status: 'ACTIVE',
      },
    }).as('league');

    cy.intercept('GET', '**/leagues/1/settings', {
      statusCode: 200,
      body: {
        draft_year: 2026,
        roster_size: 14,
      },
    }).as('settings');

    cy.intercept('GET', '**/leagues/1/budgets?*', {
      statusCode: 200,
      body: [
        { owner_id: 5, total_budget: 200 },
        { owner_id: 6, total_budget: 200 },
      ],
    }).as('budgets');

    cy.visit('/draft', {
      onBeforeLoad(win) {
        win.localStorage.setItem('fantasyToken', 'e2e-token');
        win.localStorage.setItem('user_id', '5');
        win.localStorage.setItem('fantasyLeagueId', '1');
      },
    });

    cy.wait('@authMe');
    cy.wait('@owners');
    cy.wait('@players');
    cy.wait('@history');

    cy.contains('Draft Board').should('be.visible');
    cy.get('[data-testid="auction-top-row"]').should('exist');
    cy.contains('SOLD!').should('be.visible');
  });
});
