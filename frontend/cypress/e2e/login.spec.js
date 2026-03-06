describe('Login + League selection (E2E stubbed)', () => {
  it('logs in and selects a league using network stubs', () => {
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

    cy.intercept('GET', '**/auth/me', {
      statusCode: 200,
      body: {
        user_id: 5,
        username: 'e2e-user',
        is_commissioner: false,
        league_id: 1,
      },
    }).as('meAfterLogin');

    // Intercept token request
    cy.intercept('POST', '**/auth/token', {
      statusCode: 200,
      body: { access_token: 'e2e-token', owner_id: 5, league_id: 1 },
    }).as('tokenRequest');

    cy.visit('/');

    // Fill login form
    cy.get('input[placeholder="Enter username"]')
      .should('be.visible')
      .invoke('val', 'e2e')
      .trigger('input')
      .trigger('change');

    cy.get('input[placeholder="Enter password"]')
      .should('be.visible')
      .invoke('val', 'password')
      .trigger('input')
      .trigger('change');

    cy.get('button[type="submit"]').click();

    cy.wait('@tokenRequest');
    cy.wait('@meAfterLogin');

    // Should navigate into the app layout (login form should be gone)
    cy.get('input[placeholder="Enter username"]').should('not.exist');
  });
});
