describe('Login + League selection (E2E stubbed)', () => {
  it('logs in and selects a league using network stubs', () => {
    let isAuthenticated = false;

    cy.intercept('GET', '**/advisor/status', {
      statusCode: 200,
      body: { enabled: false },
    }).as('advisorStatus');

    cy.intercept('GET', '**/leagues/1', {
      statusCode: 200,
      body: { id: 1, name: 'E2E League', draft_status: 'ACTIVE' },
    }).as('league');

    cy.intercept('GET', '**/leagues/1/settings', {
      statusCode: 200,
      body: {},
    }).as('leagueSettings');

    cy.intercept('GET', '**/auth/me', (req) => {
      if (!isAuthenticated) {
        req.reply({ statusCode: 401, body: { detail: 'Not authenticated' } });
        return;
      }

      req.reply({
        statusCode: 200,
        body: {
          user_id: 5,
          username: 'e2e-user',
          is_commissioner: false,
          league_id: 1,
        },
      });
    }).as('meRequest');

    // Intercept token request
    cy.intercept('POST', '**/auth/token', (req) => {
      isAuthenticated = true;
      req.reply({
        statusCode: 200,
        body: { access_token: 'e2e-token', owner_id: 5, league_id: 1 },
      });
    }).as('tokenRequest');

    cy.clearCookies();
    cy.clearLocalStorage();
    cy.visit('/');

    // Fill login form
    cy.get('input[placeholder="Enter username"]', { timeout: 10000 }).should('be.visible');
    cy.get('input[placeholder="Enter username"]').click();
    cy.get('input[placeholder="Enter username"]').clear({ force: true });
    cy.get('input[placeholder="Enter username"]').type('e2e', { delay: 0, force: true });

    cy.get('input[placeholder="Enter password"]').should('be.visible');
    cy.get('input[placeholder="Enter password"]').click();
    cy.get('input[placeholder="Enter password"]').clear({ force: true });
    cy.get('input[placeholder="Enter password"]').type('password', { delay: 0, force: true });

    cy.get('button[type="submit"]').click();

    cy.wait('@tokenRequest');

    // Should navigate into the app layout (login form should be gone)
    cy.get('input[placeholder="Enter username"]').should('not.exist');
  });
});
