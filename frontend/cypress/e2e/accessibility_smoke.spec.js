describe('Accessibility smoke checks', () => {
  it('verifies baseline accessibility expectations on login page', () => {
    cy.visit('/');

    // Validate basic page structure and content rendered for assistive tech users.
    cy.get('form').should('exist');
    cy.get('h1, h2').should('have.length.at.least', 1);

    cy.get('img').each(($img) => {
      const alt = $img.attr('alt') || '';
      expect(alt.trim(), 'image alt text').to.not.equal('');
    });

    cy.get('label').should('have.length.at.least', 3);

    cy.get('input').each(($input) => {
      const type = ($input.attr('type') || 'text').toLowerCase();
      if (type === 'hidden') {
        return;
      }

      const ariaLabel = ($input.attr('aria-label') || '').trim();
      const placeholder = ($input.attr('placeholder') || '').trim();
      const id = ($input.attr('id') || '').trim();

      // Require at least one of: explicit aria-label, placeholder hint, or id for label association.
      expect(Boolean(ariaLabel || placeholder || id), 'input accessibility hint').to.equal(true);
    });
  });
});
