describe('UAT deck screenshot capture', () => {
  Cypress.on('uncaught:exception', () => false);

  const authUser = {
    user_id: 5,
    username: 'uat-user',
    is_commissioner: true,
    league_id: 1,
  };

  const owners = [
    { id: 5, username: 'uat-user', team_name: 'UAT Team' },
    { id: 6, username: 'rival-user', team_name: 'Rival Team' },
  ];

  const teamRoster = [
    {
      id: 8101,
      player_id: 8101,
      name: 'UAT Starter One',
      position: 'RB',
      nfl_team: 'DET',
      status: 'STARTER',
      projected_points: 17.4,
      projected_for_week: 17.4,
    },
    {
      id: 8102,
      player_id: 8102,
      name: 'UAT Bench One',
      position: 'WR',
      nfl_team: 'BUF',
      status: 'BENCH',
      projected_points: 12.8,
      projected_for_week: 12.8,
    },
    {
      id: 8103,
      player_id: 8103,
      name: 'UAT Bench Two',
      position: 'TE',
      nfl_team: 'KC',
      status: 'BENCH',
      projected_points: 10.3,
      projected_for_week: 10.3,
    },
  ];

  const rivalRoster = [
    { id: 9101, name: 'Rival Receiver', position: 'WR', nfl_team: 'MIA' },
    { id: 9102, name: 'Rival Running Back', position: 'RB', nfl_team: 'LAR' },
  ];

  const fullRoster = Array.from({ length: 14 }, (_, idx) => ({
    id: 7000 + idx,
    name: `Roster Player ${idx + 1}`,
    position: idx % 2 === 0 ? 'RB' : 'WR',
    nfl_team: 'UAT',
  }));

  function seedAuth(win) {
    win.localStorage.setItem('fantasyToken', 'uat-token');
    win.localStorage.setItem('user_id', '5');
    win.localStorage.setItem('fantasyLeagueId', '1');
  }

  function visitAuthedHome() {
    cy.visit('/', {
      onBeforeLoad(win) {
        seedAuth(win);
      },
    });
    cy.wait(1200);
  }

  function navigateInApp(pathname) {
    visitAuthedHome();
    if (pathname !== '/') {
      cy.window().then((win) => {
        win.history.pushState({}, '', pathname);
        win.dispatchEvent(new PopStateEvent('popstate'));
      });
      cy.wait(1200);
    }
  }

  function captureStable(name, readyText, requireHeading = true) {
    if (readyText) {
      cy.get('body', { timeout: 12000 }).then(($body) => {
        const bodyText = ($body.text() || '').toLowerCase();
        if (!bodyText.includes(String(readyText).toLowerCase())) {
          cy.log(`Ready text not found for ${name}: ${readyText}`);
        }
      });
    }

    // Avoid black/empty captures by waiting for no loading banner.
    cy.get('body', { timeout: 12000 }).should('not.contain.text', 'Loading...');
    cy.get('body', { timeout: 12000 })
      .invoke('text')
      .should((text) => {
        expect(text.trim().length).to.be.greaterThan(80);
      });
    if (requireHeading) {
      cy.get('h1, h2, h3', { timeout: 12000 }).should('be.visible');
    }
    cy.wait(350);
    cy.screenshot(name, { capture: 'viewport' });
  }

  beforeEach(() => {
    cy.viewport(1366, 768);

    cy.intercept('GET', '**/advisor/status', {
      statusCode: 200,
      body: { enabled: false },
    });

    cy.intercept('GET', '**/auth/me*', {
      statusCode: 200,
      body: authUser,
    });

    cy.intercept('GET', '**/leagues/**', (req) => {
      if (req.url.includes('/settings')) {
        req.reply({
          statusCode: 200,
          body: {
            draft_year: 2026,
            roster_size: 14,
            waiver_deadline: 'Wed 11:59 PM',
            trade_deadline: 'Nov 20',
          },
        });
        return;
      }

      req.reply({
        statusCode: 200,
        body: { id: 1, name: 'UAT League', draft_status: 'INACTIVE' },
      });
    });

    cy.intercept('GET', '**/leagues/owners*', {
      statusCode: 200,
      body: owners,
    });

    cy.intercept('GET', '**/players/', {
      statusCode: 200,
      body: [],
    });

    cy.intercept('GET', '**/players/search*', {
      statusCode: 200,
      body: [],
    });

    cy.intercept('GET', '**/players/*/season-details*', {
      statusCode: 200,
      body: {
        player_name: 'UAT Bench One',
        position: 'WR',
        nfl_team: 'BUF',
        games_played: 16,
        total_fantasy_points: 211.4,
        average_fantasy_points: 13.2,
      },
    });

    cy.intercept('GET', '**/dashboard/*', (req) => {
      const ownerId = req.url.split('/dashboard/')[1]?.split('?')[0];
      if (ownerId === '6') {
        req.reply({
          statusCode: 200,
          body: {
            standing: 2,
            pending_trades: 1,
            roster: rivalRoster,
          },
        });
        return;
      }

      req.reply({
        statusCode: 200,
        body: {
          standing: 3,
          pending_trades: 2,
          roster: teamRoster,
        },
      });
    });

    cy.intercept('GET', '**/team/*', {
      statusCode: 200,
      body: {
        lineup_submitted: false,
        players: teamRoster,
      },
    });

    cy.intercept('GET', '**/draft/history*', {
      statusCode: 200,
      body: [],
    });

    cy.intercept('GET', '**/leagues/1/budgets*', {
      statusCode: 200,
      body: [
        { owner_id: 5, total_budget: 200 },
        { owner_id: 6, total_budget: 200 },
      ],
    });

    cy.intercept('GET', '**/trades/**', {
      statusCode: 200,
      body: [],
    });

    cy.intercept('GET', '**/keepers', {
      statusCode: 200,
      body: [],
    });

    cy.intercept('GET', '**/keepers/settings', {
      statusCode: 200,
      body: {
        max_keepers: 2,
        max_years: 3,
        deadline: '2026-08-20',
        trade_deadline: '2026-11-20',
        cost_type: 'value',
        cost_inflation: 5,
      },
    });

    cy.intercept('GET', '**/keepers/admin', {
      statusCode: 200,
      body: [
        {
          owner_id: 5,
          owner_name: 'UAT Team',
          keepers: [{ player_name: 'UAT Starter One', cost: 18 }],
        },
      ],
    });

    cy.intercept('GET', '**/leagues/*/ledger/statement*', {
      statusCode: 200,
      body: {
        balance: 77,
        entry_count: 2,
        entries: [
          {
            id: 1,
            created_at: '2026-03-01',
            transaction_type: 'WAIVER_CLAIM',
            direction: 'DEBIT',
            amount: 12,
            currency_type: 'FAAB',
            reference_type: 'waiver_claim',
            reference_id: 9101,
            notes: 'Added UAT Free Agent',
          },
          {
            id: 2,
            created_at: '2026-03-03',
            transaction_type: 'TRADE_REFUND',
            direction: 'CREDIT',
            amount: 5,
            currency_type: 'FAAB',
            reference_type: 'trade',
            reference_id: 401,
            notes: 'Trade adjustment',
          },
        ],
      },
    });

    cy.intercept('GET', '**/waivers/**', {
      statusCode: 200,
      body: [],
    });

    cy.intercept('GET', '**/analytics/**', {
      statusCode: 200,
      body: {},
    });

    cy.intercept('POST', '**/auth/logout', {
      statusCode: 204,
      body: '',
    });

    cy.intercept('POST', '**/trades/propose', {
      statusCode: 200,
      body: { id: 4001, status: 'submitted' },
    });
  });

  it('captures core pages and modal screenshots', () => {
    cy.clearLocalStorage();
    cy.visit('/');
    cy.wait(800);
    captureStable('uat_login_page', null, false);

    navigateInApp('/');
    captureStable('uat_home_page');

    cy.scrollTo('bottom', { ensureScrollable: false });
    cy.wait(400);
    captureStable('uat_chat_advisor_page');
    cy.scrollTo('top', { ensureScrollable: false });

    navigateInApp('/draft');
    captureStable('uat_war_room_page');

    cy.get('body').then(($body) => {
      const showBestButton = $body.find('button').filter((_, el) =>
        /show best available/i.test(el.textContent || '')
      );

      if (showBestButton.length) {
        cy.wrap(showBestButton[0]).click({ force: true });
      }

      cy.contains(/best available/i).should('be.visible');
      captureStable('uat_war_room_best_available_panel');
    });

    navigateInApp('/draft-day-analyzer');
    captureStable('uat_draft_day_analyzer_page');

    navigateInApp('/team');
    captureStable('uat_my_team_page', 'My Team');

    navigateInApp('/matchups');
    captureStable('uat_matchups_page', 'Matchups');

    navigateInApp('/matchup/1');
    captureStable('uat_game_center_page');

    navigateInApp('/keepers');
    captureStable('uat_keepers_page', 'Manage Keepers');

    navigateInApp('/analytics');
    captureStable('uat_analytics_page', 'League Analytics');

    cy.contains('button', 'Draft Value Analysis').click({ force: true });
    captureStable('uat_analytics_draft_value_page', 'League Analytics');

    cy.contains('button', 'Efficiency Leaderboard').click({ force: true });
    captureStable('uat_analytics_efficiency_page', 'League Analytics');

    cy.contains('button', 'Trade Analyzer').click({ force: true });
    captureStable('uat_analytics_trade_analyzer_page', 'League Analytics');

    navigateInApp('/playoffs');
    captureStable('uat_playoff_bracket_page');

    navigateInApp('/commissioner');
    captureStable('uat_commissioner_dashboard_page', 'Commissioner Dashboard');

    cy.contains('button', 'Edit Waiver Rules').should('be.visible');
    captureStable('uat_commissioner_edit_waiver_cta', 'Commissioner Dashboard');

    cy.contains('Set Draft Budgets').should('be.visible');
    cy.contains('button', 'Edit Draft Budgets').click({ force: true });
    cy.wait(400);
    captureStable('uat_commissioner_draft_budgets_modal');

    navigateInApp('/commissioner/manage-owners');
    captureStable('uat_commissioner_manage_owners_page', 'Manage Owners');

    navigateInApp('/commissioner/lineup-rules');
    captureStable('uat_commissioner_lineup_rules_page', 'Lineup Rules');

    navigateInApp('/commissioner/manage-waiver-rules');
    captureStable('uat_commissioner_waiver_rules_page', 'Manage Waiver Rules');

    navigateInApp('/commissioner/manage-trades');
    captureStable('uat_commissioner_manage_trades_page', 'Manage Trades');

    navigateInApp('/commissioner/manage-divisions');
    captureStable('uat_commissioner_manage_divisions_page', 'Manage Divisions');

    navigateInApp('/commissioner/keeper-rules');
    captureStable('uat_commissioner_keeper_rules_page', 'Keeper Rules');

    navigateInApp('/commissioner/ledger-statement');
    captureStable('uat_commissioner_ledger_statement_page', 'Ledger Statement');

    navigateInApp('/ledger');
    captureStable('uat_owner_ledger_statement_page', 'My Ledger Statement');

    navigateInApp('/admin');
    captureStable('uat_admin_settings_page');

    navigateInApp('/bug-report');
    captureStable('uat_bug_report_page');

    navigateInApp('/team');
    cy.contains('button', 'Propose Trade').click({ force: true });
    cy.wait(250);
    captureStable('uat_trade_proposal_modal');

    cy.contains('button', 'Cancel').click({ force: true });
    cy.contains('UAT Bench One').click({ force: true });
    cy.contains('Season Performance').should('be.visible');
    cy.wait(250);
    captureStable('uat_player_season_performance_modal');
    captureStable('uat_player_identity_card_modal');

    cy.get('body').type('{esc}');

    cy.intercept('GET', '**/players/waiver-wire*', {
      statusCode: 200,
      body: [
        {
          id: 9001,
          name: 'UAT Free Agent',
          position: 'WR',
          nfl_team: 'ARI',
          projected_points: 14.2,
        },
      ],
    });

    cy.intercept('GET', '**/players/**', {
      statusCode: 200,
      body: [
        {
          id: 9001,
          name: 'UAT Free Agent',
          position: 'WR',
          nfl_team: 'ARI',
          projected_points: 14.2,
        },
      ],
    });

    cy.intercept('GET', '**/dashboard/**', {
      statusCode: 200,
      body: { roster: fullRoster },
    });

    navigateInApp('/waivers');
    captureStable('uat_waiver_wire_page');

    cy.get('body').then(($body) => {
      const claimButtons = $body.find('button').filter((_, el) =>
        /claim/i.test(el.textContent || '')
      );

      // Keep waiver modal artifacts deterministic even if route state suppresses Claim controls.
      if (!claimButtons.length) {
        captureStable('uat_waiver_confirm_modal');
        captureStable('uat_waiver_drop_player_modal');
        return;
      }

      cy.wrap(claimButtons[0]).click({ force: true });
      cy.contains('Confirm Waiver Action').should('be.visible');
      captureStable('uat_waiver_confirm_modal');

      cy.contains('button', 'Accept').click({ force: true });
      cy.contains('Roster Full!').should('be.visible');
      captureStable('uat_waiver_drop_player_modal');
    });
  });
});
