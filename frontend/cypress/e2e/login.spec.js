describe('Login + League selection (E2E stubbed)', () => {
  it('logs in and selects a league using network stubs', () => {
    // Keep initial auth check unauthenticated without triggering the global 401 redirect loop
    cy.intercept('GET', '**/auth/me', { forceNetworkError: true }).as('me');

    // Intercept token request
    cy.intercept('POST', '**/auth/token', {
      statusCode: 200,
      body: { access_token: 'e2e-token', owner_id: 5, league_id: 1 },
    }).as('tokenRequest');

    cy.visit('/');

    // Initial auth probe should occur
    cy.wait('@me');

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

    // Should navigate into the app layout (login form should be gone)
    cy.get('input[placeholder="Enter username"]').should('not.exist');
  });
});
