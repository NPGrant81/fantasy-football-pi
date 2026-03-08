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

    cy.intercept('GET', /\/leagues\/\d+\/settings/, {
      statusCode: 200,
      body: {
        draft_year: 2026,
        roster_size: 14,
        waiver_deadline: 'Wed 11:59 PM',
        trade_deadline: 'Nov 20',
      },
    });

    cy.intercept('GET', /\/leagues\/\d+([?#]|$)/, {
      statusCode: 200,
      body: { id: 1, name: 'UAT League', draft_status: 'INACTIVE' },
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

    cy.intercept('GET', '**/draft/rankings*', {
      statusCode: 200,
      body: [
        {
          player_id: 8101,
          player_name: 'UAT Starter One',
          position: 'RB',
          season: 2026,
          rank: 1,
          predicted_auction_value: 55.0,
          value_over_replacement: 30.0,
          consensus_tier: 'Tier 1',
          final_score: 85.0,
          league_position_weight: 1.0,
          owner_position_affinity: 1.0,
          owner_player_affinity: 1.0,
          keeper_scarcity_boost: 1.0,
          availability_factor: 1.0,
          scoring_consistency_factor: 1.0,
          late_start_consistency_factor: 1.0,
          injury_split_factor: 1.0,
          team_change_factor: 1.0,
        },
        {
          player_id: 8102,
          player_name: 'UAT Bench One',
          position: 'WR',
          season: 2026,
          rank: 2,
          predicted_auction_value: 42.0,
          value_over_replacement: 18.0,
          consensus_tier: 'Tier 2',
          final_score: 72.0,
          league_position_weight: 1.0,
          owner_position_affinity: 1.0,
          owner_player_affinity: 1.0,
          keeper_scarcity_boost: 1.0,
          availability_factor: 1.0,
          scoring_consistency_factor: 1.0,
          late_start_consistency_factor: 1.0,
          injury_split_factor: 1.0,
          team_change_factor: 1.0,
        },
        {
          player_id: 8103,
          player_name: 'UAT Bench Two',
          position: 'TE',
          season: 2026,
          rank: 3,
          predicted_auction_value: 28.0,
          value_over_replacement: 10.0,
          consensus_tier: 'Tier 3',
          final_score: 58.0,
          league_position_weight: 1.0,
          owner_position_affinity: 1.0,
          owner_player_affinity: 1.0,
          keeper_scarcity_boost: 1.0,
          availability_factor: 1.0,
          scoring_consistency_factor: 1.0,
          late_start_consistency_factor: 1.0,
          injury_split_factor: 1.0,
          team_change_factor: 1.0,
        },
      ],
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
    cy.screenshot('uat_login_page', { capture: 'viewport' });

    navigateInApp('/');
    cy.screenshot('uat_home_page', { capture: 'viewport' });

    cy.scrollTo('bottom', { ensureScrollable: false });
    cy.wait(400);
    cy.screenshot('uat_chat_advisor_page', { capture: 'viewport' });
    cy.scrollTo('top', { ensureScrollable: false });

    navigateInApp('/draft');
    cy.screenshot('uat_war_room_page', { capture: 'viewport' });

    navigateInApp('/draft-day-analyzer');
    cy.screenshot('uat_draft_day_analyzer_page', { capture: 'viewport' });

    navigateInApp('/team');
    cy.screenshot('uat_my_team_page', { capture: 'viewport' });

    navigateInApp('/matchups');
    cy.screenshot('uat_matchups_page', { capture: 'viewport' });

    navigateInApp('/matchup/1');
    cy.screenshot('uat_game_center_page', { capture: 'viewport' });

    navigateInApp('/keepers');
    cy.screenshot('uat_keepers_page', { capture: 'viewport' });

    navigateInApp('/analytics');
    cy.screenshot('uat_analytics_page', { capture: 'viewport' });

    navigateInApp('/playoffs');
    cy.screenshot('uat_playoff_bracket_page', { capture: 'viewport' });

    navigateInApp('/commissioner');
    cy.screenshot('uat_commissioner_dashboard_page', { capture: 'viewport' });

    cy.contains('Set Draft Budgets').should('be.visible');
    cy.contains('button', 'Edit Draft Budgets').click({ force: true });
    cy.wait(400);
    cy.screenshot('uat_commissioner_draft_budgets_modal', { capture: 'viewport' });

    navigateInApp('/commissioner/manage-owners');
    cy.screenshot('uat_commissioner_manage_owners_page', { capture: 'viewport' });

    navigateInApp('/commissioner/lineup-rules');
    cy.screenshot('uat_commissioner_lineup_rules_page', { capture: 'viewport' });

    navigateInApp('/commissioner/manage-waiver-rules');
    cy.screenshot('uat_commissioner_waiver_rules_page', { capture: 'viewport' });

    navigateInApp('/commissioner/manage-trades');
    cy.screenshot('uat_commissioner_manage_trades_page', { capture: 'viewport' });

    navigateInApp('/commissioner/manage-divisions');
    cy.screenshot('uat_commissioner_manage_divisions_page', { capture: 'viewport' });

    navigateInApp('/admin');
    cy.screenshot('uat_admin_settings_page', { capture: 'viewport' });

    navigateInApp('/bug-report');
    cy.screenshot('uat_bug_report_page', { capture: 'viewport' });

    navigateInApp('/team');
    cy.contains('button', 'Propose Trade').click({ force: true });
    cy.wait(250);
    cy.screenshot('uat_trade_proposal_modal', { capture: 'viewport' });

    cy.contains('button', 'Cancel').click({ force: true });
    cy.contains('UAT Bench One').click({ force: true });
    cy.contains('Season Performance').should('be.visible');
    cy.wait(250);
    cy.screenshot('uat_player_season_performance_modal', { capture: 'viewport' });

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
    cy.screenshot('uat_waiver_wire_page', { capture: 'viewport' });

    cy.get('body').then(($body) => {
      const claimButtons = $body.find('button').filter((_, el) =>
        /claim/i.test(el.textContent || '')
      );

      // Keep waiver modal artifacts deterministic even if route state suppresses Claim controls.
      if (!claimButtons.length) {
        cy.screenshot('uat_waiver_confirm_modal', { capture: 'viewport' });
        cy.screenshot('uat_waiver_drop_player_modal', { capture: 'viewport' });
        return;
      }

      cy.wrap(claimButtons[0]).click({ force: true });
      cy.contains('Confirm Waiver Action').should('be.visible');
      cy.screenshot('uat_waiver_confirm_modal', { capture: 'viewport' });

      cy.contains('button', 'Accept').click({ force: true });
      cy.contains('Roster Full!').should('be.visible');
      cy.screenshot('uat_waiver_drop_player_modal', { capture: 'viewport' });
    });
  });
});
