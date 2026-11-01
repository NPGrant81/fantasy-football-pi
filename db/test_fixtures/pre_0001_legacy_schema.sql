-- Historical legacy pre-Alembic schema fixture.
-- Derived from backend/models.py at commit 186dcf4652c6b29ad699e7a29f14d707a2db20d5.
-- This is a fixed test baseline, not a production schema or current ORM snapshot.

CREATE TABLE leagues (
    id SERIAL NOT NULL,
    name VARCHAR,
    draft_status VARCHAR,
    created_at VARCHAR,
    PRIMARY KEY (id)
);
CREATE INDEX ix_leagues_id ON leagues (id);
CREATE UNIQUE INDEX ix_leagues_name ON leagues (name);

CREATE TABLE players (
    id SERIAL NOT NULL,
    name VARCHAR,
    position VARCHAR,
    nfl_team VARCHAR,
    adp FLOAT,
    projected_points FLOAT,
    gsis_id VARCHAR,
    espn_id VARCHAR,
    bye_week INTEGER,
    PRIMARY KEY (id),
    UNIQUE (gsis_id),
    UNIQUE (espn_id)
);
CREATE INDEX ix_players_name ON players (name);
CREATE INDEX ix_players_id ON players (id);

CREATE TABLE users (
    id SERIAL NOT NULL,
    username VARCHAR,
    email VARCHAR,
    hashed_password VARCHAR,
    is_superuser BOOLEAN,
    is_commissioner BOOLEAN,
    league_id INTEGER,
    division VARCHAR,
    team_name VARCHAR,
    PRIMARY KEY (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id)
);
CREATE INDEX ix_users_id ON users (id);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE league_settings (
    id SERIAL NOT NULL,
    league_id INTEGER,
    roster_size INTEGER,
    salary_cap INTEGER,
    starting_slots JSON,
    waiver_deadline VARCHAR,
    draft_year INTEGER,
    PRIMARY KEY (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id)
);
CREATE INDEX ix_league_settings_id ON league_settings (id);

CREATE TABLE scoring_rules (
    id SERIAL NOT NULL,
    league_id INTEGER,
    category VARCHAR,
    description VARCHAR,
    points FLOAT,
    PRIMARY KEY (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id)
);
CREATE INDEX ix_scoring_rules_id ON scoring_rules (id);

CREATE TABLE player_weekly_stats (
    id SERIAL NOT NULL,
    player_id INTEGER,
    season INTEGER,
    week INTEGER,
    fantasy_points FLOAT,
    stats JSON,
    source VARCHAR,
    created_at VARCHAR,
    PRIMARY KEY (id),
    CONSTRAINT uq_player_week_source UNIQUE (player_id, season, week, source),
    FOREIGN KEY(player_id) REFERENCES players (id)
);
CREATE INDEX ix_player_weekly_stats_week ON player_weekly_stats (week);
CREATE INDEX ix_player_weekly_stats_season ON player_weekly_stats (season);
CREATE INDEX ix_player_weekly_stats_id ON player_weekly_stats (id);

CREATE TABLE draft_picks (
    id SERIAL NOT NULL,
    year INTEGER,
    round_num INTEGER,
    pick_num INTEGER,
    amount INTEGER,
    session_id VARCHAR,
    current_status VARCHAR,
    timestamp VARCHAR,
    owner_id INTEGER,
    player_id INTEGER,
    league_id INTEGER,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES users (id),
    FOREIGN KEY(player_id) REFERENCES players (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id)
);
CREATE INDEX ix_draft_picks_id ON draft_picks (id);

CREATE TABLE draft_budgets (
    id SERIAL NOT NULL,
    league_id INTEGER,
    owner_id INTEGER,
    year INTEGER,
    total_budget INTEGER,
    PRIMARY KEY (id),
    CONSTRAINT uq_budget_league_owner_year UNIQUE (league_id, owner_id, year),
    FOREIGN KEY(league_id) REFERENCES leagues (id),
    FOREIGN KEY(owner_id) REFERENCES users (id)
);
CREATE INDEX ix_draft_budgets_year ON draft_budgets (year);
CREATE INDEX ix_draft_budgets_id ON draft_budgets (id);

CREATE TABLE matchups (
    id SERIAL NOT NULL,
    week INTEGER,
    league_id INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score FLOAT,
    away_score FLOAT,
    is_completed BOOLEAN,
    PRIMARY KEY (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id),
    FOREIGN KEY(home_team_id) REFERENCES users (id),
    FOREIGN KEY(away_team_id) REFERENCES users (id)
);
CREATE INDEX ix_matchups_week ON matchups (week);
CREATE INDEX ix_matchups_id ON matchups (id);

CREATE TABLE waiver_claims (
    id SERIAL NOT NULL,
    league_id INTEGER,
    user_id INTEGER,
    player_id INTEGER,
    drop_player_id INTEGER,
    bid_amount INTEGER,
    status VARCHAR,
    PRIMARY KEY (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id),
    FOREIGN KEY(user_id) REFERENCES users (id),
    FOREIGN KEY(player_id) REFERENCES players (id),
    FOREIGN KEY(drop_player_id) REFERENCES players (id)
);
CREATE INDEX ix_waiver_claims_id ON waiver_claims (id);

CREATE TABLE bug_reports (
    id SERIAL NOT NULL,
    user_id INTEGER,
    email VARCHAR,
    title VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    page_name VARCHAR,
    issue_type VARCHAR,
    page_url VARCHAR,
    github_issue_url VARCHAR,
    status VARCHAR,
    created_at VARCHAR,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_bug_reports_id ON bug_reports (id);

CREATE TABLE trade_proposals (
    id SERIAL NOT NULL,
    league_id INTEGER NOT NULL,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    offered_player_id INTEGER NOT NULL,
    requested_player_id INTEGER NOT NULL,
    note VARCHAR,
    status VARCHAR,
    created_at VARCHAR,
    PRIMARY KEY (id),
    FOREIGN KEY(league_id) REFERENCES leagues (id),
    FOREIGN KEY(from_user_id) REFERENCES users (id),
    FOREIGN KEY(to_user_id) REFERENCES users (id),
    FOREIGN KEY(offered_player_id) REFERENCES players (id),
    FOREIGN KEY(requested_player_id) REFERENCES players (id)
);
CREATE INDEX ix_trade_proposals_id ON trade_proposals (id);

CREATE TABLE lineup_submissions (
    id SERIAL NOT NULL,
    league_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    season INTEGER,
    week INTEGER,
    submitted_at VARCHAR,
    PRIMARY KEY (id),
    CONSTRAINT uq_lineup_submission_week UNIQUE (league_id, owner_id, season, week),
    FOREIGN KEY(league_id) REFERENCES leagues (id),
    FOREIGN KEY(owner_id) REFERENCES users (id)
);
CREATE INDEX ix_lineup_submissions_id ON lineup_submissions (id);
CREATE INDEX ix_lineup_submissions_season ON lineup_submissions (season);
CREATE INDEX ix_lineup_submissions_week ON lineup_submissions (week);
