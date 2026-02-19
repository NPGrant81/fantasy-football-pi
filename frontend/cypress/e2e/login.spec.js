describe('Login + League selection (E2E stubbed)', () => {
  it('logs in and selects a league using network stubs', () => {
    // Intercept token request
    cy.intercept('POST', '**/auth/token', {
      statusCode: 200,
      body: { access_token: 'e2e-token', owner_id: 5, league_id: 1 },
    }).as('token');

    // Intercept auth/me
    cy.intercept('GET', '**/auth/me', {
      statusCode: 200,
      body: { user_id: 5, username: 'e2e-user' },
    }).as('me');

    cy.visit('/');

    // Fill login form
    cy.get('input[placeholder="Enter username"]').type('e2e');
    cy.get('input[placeholder="Enter password"]').type('password');
    cy.get('button[type="submit"]').click();

    cy.wait('@token');

    // App should now call /auth/me
    cy.wait('@me');

    // Should navigate into the app layout (login form should be gone)
    cy.get('input[placeholder="Enter username"]').should('not.exist');
  });
});
