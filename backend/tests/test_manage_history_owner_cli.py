"""Tests for history owner backfill CLI commands in backend/manage.py."""

from unittest.mock import MagicMock, patch
import csv
import tempfile
import os

from click.testing import CliRunner

import backend.manage as manage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_league(league_id=60, name="Post Pacific League"):
    league = MagicMock()
    league.id = league_id
    league.name = name
    return league


def _make_row(id, season, team_name, owner_name=None, owner_id=None, notes=None):
    row = MagicMock()
    row.id = id
    row.season = season
    row.team_name = team_name
    row.owner_name = owner_name
    row.owner_id = owner_id
    row.notes = notes
    return row


# ---------------------------------------------------------------------------
# history-owner-gap-report
# ---------------------------------------------------------------------------

class TestHistoryOwnerGapReport:
    def _invoke(self, db_session, *extra_args):
        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db_session):
            return runner.invoke(manage.cli, ["history-owner-gap-report"] + list(extra_args))

    def _make_db(self, league, rows):
        db = MagicMock()
        db.__enter__ = lambda s: s
        db.__exit__ = MagicMock(return_value=False)
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = rows
        db.query.side_effect = lambda model: league if model.__name__ == "League" else q
        # league lookup
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.order_by.return_value = map_q
        map_q.all.return_value = rows

        def query_side_effect(model):
            if hasattr(model, "__tablename__") and model.__tablename__ == "leagues":
                return league_q
            return map_q

        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)
        return db

    def test_missing_required_league_id(self):
        runner = CliRunner()
        result = runner.invoke(manage.cli, ["history-owner-gap-report"])
        assert result.exit_code != 0
        assert "--league-id" in result.output or "Missing option" in result.output

    def test_league_not_found(self):
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = None
        db.query = MagicMock(return_value=league_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            result = runner.invoke(manage.cli, ["history-owner-gap-report", "--league-id", "999"])

        assert result.exit_code != 0
        assert "999" in result.output

    def test_all_resolved(self):
        league = _make_league()
        rows = [
            _make_row(1, 2020, "Team A", "Jane Smith"),
            _make_row(2, 2020, "Team B", "John Doe"),
        ]
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.order_by.return_value = map_q
        map_q.all.return_value = rows
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            result = runner.invoke(manage.cli, ["history-owner-gap-report", "--league-id", "60"])

        assert result.exit_code == 0
        assert "No placeholder mappings found" in result.output
        assert "Resolved rows:       2" in result.output

    def test_placeholder_rows_reported(self):
        league = _make_league()
        # row where owner_name == team_name is a placeholder
        rows = [
            _make_row(1, 2020, "Team A", "Team A"),
            _make_row(2, 2020, "Team B", "Jane Smith"),
        ]
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.order_by.return_value = map_q
        map_q.all.return_value = rows
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            result = runner.invoke(manage.cli, ["history-owner-gap-report", "--league-id", "60"])

        assert result.exit_code == 0
        assert "Placeholder rows:    1" in result.output
        assert "Resolved rows:       1" in result.output

    def test_json_output_written(self):
        league = _make_league()
        rows = [_make_row(1, 2020, "Team A", "Team A")]
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.order_by.return_value = map_q
        map_q.all.return_value = rows
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                result = runner.invoke(
                    manage.cli,
                    ["history-owner-gap-report", "--league-id", "60", "--json-output", "out.json"],
                )
                assert result.exit_code == 0
                assert os.path.exists("out.json")
                import json
                data = json.loads(open("out.json").read())
                assert data["league_id"] == 60
                assert data["placeholders"] == 1


# ---------------------------------------------------------------------------
# export-history-owner-seed
# ---------------------------------------------------------------------------

class TestExportHistoryOwnerSeed:
    def test_missing_league_id(self):
        runner = CliRunner()
        result = runner.invoke(manage.cli, ["export-history-owner-seed", "--output", "/tmp/x.csv"])
        assert result.exit_code != 0

    def test_missing_output(self):
        runner = CliRunner()
        result = runner.invoke(manage.cli, ["export-history-owner-seed", "--league-id", "60"])
        assert result.exit_code != 0

    def test_exports_all_rows(self):
        league = _make_league()
        rows = [
            _make_row(1, 2020, "Team A", "Jane Smith"),
            _make_row(2, 2020, "Team B", "Team B"),
        ]
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.order_by.return_value = map_q
        map_q.all.return_value = rows
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                result = runner.invoke(
                    manage.cli,
                    ["export-history-owner-seed", "--league-id", "60", "--output", "seed.csv"],
                )
                assert result.exit_code == 0
                assert "Exported 2 rows" in result.output
                with open("seed.csv") as fh:
                    reader = csv.DictReader(fh)
                    exported = list(reader)
                assert len(exported) == 2

    def test_placeholders_only_filter(self):
        league = _make_league()
        rows = [
            _make_row(1, 2020, "Team A", "Jane Smith"),
            _make_row(2, 2020, "Team B", "Team B"),  # placeholder
            _make_row(3, 2020, "Team C", None),        # empty = placeholder
        ]
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.order_by.return_value = map_q
        map_q.all.return_value = rows
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                result = runner.invoke(
                    manage.cli,
                    ["export-history-owner-seed", "--league-id", "60", "--output", "seed.csv", "--placeholders-only"],
                )
                assert result.exit_code == 0
                assert "Exported 2 rows" in result.output


# ---------------------------------------------------------------------------
# import-history-owner-seed
# ---------------------------------------------------------------------------

class TestImportHistoryOwnerSeed:
    def _write_csv(self, path, rows):
        fieldnames = ["id", "season", "team_name", "owner_name", "owner_id", "notes"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    def test_dry_run_by_default(self):
        """--apply not passed means dry-run: no db.commit() called."""
        league = _make_league()
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.first.return_value = None
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                self._write_csv("seed.csv", [
                    {"id": "", "season": "2020", "team_name": "Team A", "owner_name": "Jane Smith", "owner_id": "", "notes": ""},
                ])
                result = runner.invoke(
                    manage.cli,
                    ["import-history-owner-seed", "--league-id", "60", "--csv", "seed.csv"],
                )

        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "Re-run with --apply" in result.output
        db.commit.assert_not_called()

    def test_apply_commits(self):
        league = _make_league()
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.first.return_value = None
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                self._write_csv("seed.csv", [
                    {"id": "", "season": "2020", "team_name": "Team A", "owner_name": "Jane Smith", "owner_id": "", "notes": ""},
                ])
                result = runner.invoke(
                    manage.cli,
                    ["import-history-owner-seed", "--league-id", "60", "--csv", "seed.csv", "--apply"],
                )

        assert result.exit_code == 0
        assert "applied" in result.output
        db.commit.assert_called_once()

    def test_skips_empty_owner_name(self):
        league = _make_league()
        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.first.return_value = None
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                self._write_csv("seed.csv", [
                    {"id": "", "season": "2020", "team_name": "Team A", "owner_name": "", "owner_id": "", "notes": ""},
                ])
                result = runner.invoke(
                    manage.cli,
                    ["import-history-owner-seed", "--league-id", "60", "--csv", "seed.csv"],
                )

        assert result.exit_code == 0
        assert "Skipped" in result.output

    def test_update_clears_notes_when_empty(self):
        """When notes is empty in CSV, the existing row's notes should be set to None (cleared)."""
        league = _make_league()
        existing = _make_row(1, 2020, "Team A", "Team A", notes="old note")

        db = MagicMock()
        db.close = MagicMock()
        league_q = MagicMock()
        league_q.filter.return_value = league_q
        league_q.first.return_value = league
        # first query by id returns existing; second by key also returns existing
        map_q = MagicMock()
        map_q.filter.return_value = map_q
        map_q.first.return_value = existing
        db.query = MagicMock(side_effect=lambda m: league_q if m is manage.models.League else map_q)

        runner = CliRunner()
        with patch("backend.manage.SessionLocal", return_value=db):
            with runner.isolated_filesystem():
                self._write_csv("seed.csv", [
                    {"id": "1", "season": "2020", "team_name": "Team A", "owner_name": "Jane Smith", "owner_id": "", "notes": ""},
                ])
                result = runner.invoke(
                    manage.cli,
                    ["import-history-owner-seed", "--league-id", "60", "--csv", "seed.csv", "--apply"],
                )

        assert result.exit_code == 0
        # notes should have been set to None (empty CSV value clears the field)
        assert existing.notes is None

    def test_missing_league_id_option(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("seed.csv", "w") as f:
                f.write("id,season,team_name,owner_name,owner_id,notes\n")
            result = runner.invoke(manage.cli, ["import-history-owner-seed", "--csv", "seed.csv"])
        assert result.exit_code != 0
