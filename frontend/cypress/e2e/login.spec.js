describe('Login + League selection (E2E stubbed)', () => {
  it('logs in and selects a league using network stubs', () => {
    // Intercept token request
    cy.intercept('POST', '/auth/token', {
      statusCode: 200,
      body: { access_token: 'e2e-token', owner_id: 5, league_id: 1 },
    }).as('token');

    // Intercept auth/me
    cy.intercept('GET', '/auth/me', {
      statusCode: 200,
      body: { user_id: 5, username: 'e2e-user' },
    }).as('me');

    // Intercept leagues
    cy.intercept('GET', '/leagues/', {
      statusCode: 200,
      body: [{ id: 1, name: 'E2E League' }],
    }).as('leagues');

    cy.visit('/');

    // Fill login form
    cy.get('input[placeholder="Enter username"]').type('e2e');
    cy.get('input[placeholder="Enter password"]').type('password');
    cy.get('button[type="submit"]').click();

    cy.wait('@token');

    // App should now call /auth/me and then load leagues (if no league saved)
    cy.wait('@me');
    cy.wait('@leagues');

    // If LeagueSelector appears, select the league
    cy.contains('E2E League').click();

    // Should navigate into app layout (Dashboard text mocked in unit tests)
    cy.contains('WAR ROOM LOGIN').should('not.exist');
  });
});
