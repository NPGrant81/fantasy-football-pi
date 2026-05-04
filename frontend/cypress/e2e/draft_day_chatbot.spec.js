describe('Draft Day Chatbot flow', () => {
  const authUser = {
    user_id: 5,
    username: 'chat-e2e-user',
    is_commissioner: true,
    league_id: 1,
  };

  const owners = [
    { id: 5, username: 'chat-e2e-user', team_name: 'Chat Team' },
    { id: 6, username: 'rival-owner', team_name: 'Rival Team' },
  ];

  const players = [
    { id: 101, name: 'Player A', nfl_team: 'BUF', position: 'WR', espn_id: '101' },
    { id: 102, name: 'Player B', nfl_team: 'KC', position: 'WR', espn_id: '102' },
    { id: 103, name: 'Player C', nfl_team: 'SF', position: 'RB', espn_id: '103' },
  ];

  const rankings = [
    {
      player_id: 101,
      player_name: 'Player A',
      position: 'WR',
      predicted_auction_value: 50,
      price_min: 45,
      price_avg: 50,
      price_max: 56,
      adp: 7.2,
      confidence_score: 82,
      consensus_tier: 'A',
      final_score: 85,
    },
    {
      player_id: 102,
      player_name: 'Player B',
      position: 'WR',
      predicted_auction_value: 42,
      price_min: 38,
      price_avg: 42,
      price_max: 47,
      adp: 12.3,
      confidence_score: 76,
      consensus_tier: 'B',
      final_score: 73,
    },
    {
      player_id: 103,
      player_name: 'Player C',
      position: 'RB',
      predicted_auction_value: 39,
      price_min: 34,
      price_avg: 39,
      price_max: 44,
      adp: 18.7,
      confidence_score: 70,
      consensus_tier: 'B',
      final_score: 69,
    },
  ];

  beforeEach(() => {
    cy.viewport(1366, 768);

    cy.intercept('GET', '**/advisor/status', {
      statusCode: 200,
      body: { enabled: false },
    });

    cy.intercept('POST', '**/analytics/visit', {
      statusCode: 200,
      body: { ok: true },
    });

    cy.intercept('GET', '**/auth/me*', {
      statusCode: 200,
      body: authUser,
    }).as('authMe');

    cy.intercept('GET', '**/leagues/owners*', {
      statusCode: 200,
      body: owners,
    }).as('owners');

    cy.intercept('GET', '**/players/', {
      statusCode: 200,
      body: players,
    }).as('players');

    cy.intercept('GET', '**/leagues/1/settings', {
      statusCode: 200,
      body: {
        draft_year: 2026,
        roster_size: 14,
        starting_slots: {
          MAX_QB: 2,
          MAX_RB: 5,
          MAX_WR: 5,
          MAX_TE: 2,
          MAX_DEF: 1,
          MAX_K: 1,
        },
      },
    }).as('settings');

    cy.intercept('GET', '**/draft/history?*', {
      statusCode: 200,
      body: [],
    }).as('history');

    cy.intercept('GET', '**/draft/rankings?*', {
      statusCode: 200,
      body: rankings,
    }).as('rankings');

    cy.intercept('POST', '**/draft/model/predict', {
      statusCode: 200,
      body: {
        recommendations: [
          {
            player_name: 'Player A',
            position: 'WR',
            recommended_bid: 50,
            predicted_value: 50,
            risk_score: 18,
            value_score: 50,
            tier: 'A',
            flags: [],
          },
        ],
      },
    }).as('predict');

    cy.intercept('POST', '**/advisor/draft-day/query', (req) => {
      if (req.body?.question?.toLowerCase()?.includes('compare')) {
        req.reply({
          statusCode: 200,
          body: {
            event_type: 'user_query',
            message_type: 'comparison',
            headline: 'Comparison: Player A vs Player B',
            body: 'Preferred target right now is Player A.',
            alerts: [],
            quick_actions: ['Compare', 'Simulate', 'Explain'],
          },
        });
        return;
      }

      req.reply({
        statusCode: 200,
        body: {
          event_type: 'user_query',
          message_type: 'recommendation',
          headline: 'Draft Day answer',
          body: 'For Player A, recommended bid cap is $50.00.',
          recommended_bid: 50,
          value_tier: 'A',
          risk_score: 22,
          bidding_war_likelihood: 48,
          suggested_alternatives: [
            { player_id: 102, player_name: 'Player B', position: 'WR', predicted_value: 42, tier: 'B' },
          ],
          alerts: [],
          quick_actions: ['Compare', 'Simulate', 'Explain'],
        },
      });
    }).as('chatQuery');

    cy.intercept('POST', '**/advisor/draft-day/event', {
      statusCode: 200,
      body: {
        event_type: 'nomination',
        message_type: 'recommendation',
        headline: 'Nomination guidance: Player A',
        body: 'Recommended bid cap is $50.00.',
        recommended_bid: 50,
        value_tier: 'A',
        risk_score: 22,
        bidding_war_likelihood: 48,
        suggested_alternatives: [],
        alerts: [],
        quick_actions: ['Compare', 'Simulate', 'Explain'],
      },
    }).as('chatEvent');
  });

  it('sends a chat query and renders advisor response with quick actions', () => {
    cy.visit('/draft-day-analyzer', {
      onBeforeLoad(win) {
        win.localStorage.setItem('fantasyToken', 'chat-token');
        win.localStorage.setItem('user_id', '5');
        win.localStorage.setItem('fantasyLeagueId', '1');
      },
    });

    cy.wait('@authMe');
    cy.wait('@owners');
    cy.wait('@players');
    cy.wait('@settings');
    cy.wait('@history');
    cy.wait('@rankings');
    cy.wait('@predict');

    cy.get('[data-testid="draft-day-chat-panel"]').should('be.visible');

    cy.get('input[aria-label="Chat input"]')
      .should('be.enabled')
      .type('Should I push on Player A?');

    cy.contains('button', 'Send').click();

    cy.wait('@chatQuery').its('request.body').should((body) => {
      expect(body.owner_id).to.equal(5);
      expect(body.league_id).to.equal(1);
      expect(body.player_id).to.equal(101);
      expect(body.question).to.equal('Should I push on Player A?');
      expect(body.draft_state).to.exist;
    });

    cy.contains('Draft Day answer').should('be.visible');
    cy.contains('For Player A, recommended bid cap is $50.00.').should('be.visible');

    cy.contains('button', 'Compare').click();
    cy.wait('@chatQuery').its('request.body').should((body) => {
      expect(body.compared_player_id).to.equal(102);
      expect(String(body.question || '').toLowerCase()).to.contain('compare');
    });

    cy.contains('Comparison: Player A vs Player B').should('be.visible');
  });
});
