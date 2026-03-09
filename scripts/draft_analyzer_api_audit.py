from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import SessionLocal
import backend.models as models
from backend.main import ensure_runtime_schema
from backend.routers import advisor as advisor_router
from backend.routers import draft as draft_router
from backend.routers import players as players_router


@dataclass
class CheckResult:
    name: str
    status: str
    details: str


def _pick_user(db: Session) -> models.User:
    user = (
        db.query(models.User)
        .filter(models.User.league_id.isnot(None))
        .order_by(models.User.is_commissioner.desc(), models.User.id.asc())
        .first()
    )
    if not user:
        raise RuntimeError("No user with league_id found")
    return user


def _safe_call(name: str, fn):
    try:
        return CheckResult(name=name, status="PASS", details=str(fn()))
    except Exception as exc:
        return CheckResult(name=name, status="FAIL", details=str(exc))


def _dataset_checks(db: Session) -> list[CheckResult]:
    sql_map = {
        "players": "SELECT COUNT(*) FROM players",
        "draft_values_total": "SELECT COUNT(*) FROM draft_values",
        "draft_values_2025": "SELECT COUNT(*) FROM draft_values WHERE season=2025",
        "draft_values_2026": "SELECT COUNT(*) FROM draft_values WHERE season=2026",
        "player_weekly_stats_total": "SELECT COUNT(*) FROM player_weekly_stats",
        "scoring_rules": "SELECT COUNT(*) FROM scoring_rules",
        "draft_picks": "SELECT COUNT(*) FROM draft_picks",
    }

    out: list[CheckResult] = []
    for label, sql in sql_map.items():
        try:
            count = int(db.execute(text(sql)).scalar() or 0)
            status = "PASS" if count > 0 else "WARN"
            if label in {"draft_values_2025", "player_weekly_stats_total"} and count == 0:
                status = "WARN"
            out.append(CheckResult(name=f"dataset:{label}", status=status, details=f"count={count}"))
        except Exception as exc:
            out.append(CheckResult(name=f"dataset:{label}", status="FAIL", details=str(exc)))

    data_dir = Path(__file__).resolve().parents[1] / "backend" / "data"
    csv_files = ["draft_results.csv", "players.csv", "historical_rankings.csv", "draft_budget.csv"]
    for filename in csv_files:
        path = data_dir / filename
        if path.exists() and path.stat().st_size > 0:
            out.append(CheckResult(name=f"dataset_csv:{filename}", status="PASS", details=f"size={path.stat().st_size}"))
        else:
            out.append(CheckResult(name=f"dataset_csv:{filename}", status="FAIL", details="missing or empty"))

    return out


def _api_checks(db: Session, user: models.User) -> list[CheckResult]:
    checks: list[CheckResult] = []

    def rankings_2025():
        rows = draft_router.get_historical_rankings(
            season=2025,
            limit=10,
            league_id=user.league_id,
            owner_id=user.id,
            position=None,
            db=db,
            current_user=user,
        )
        return f"rows={len(rows)}"

    checks.append(_safe_call("api:/draft/rankings?season=2025", rankings_2025))

    def rankings_2026():
        rows = draft_router.get_historical_rankings(
            season=2026,
            limit=10,
            league_id=user.league_id,
            owner_id=user.id,
            position=None,
            db=db,
            current_user=user,
        )
        return f"rows={len(rows)}"

    checks.append(_safe_call("api:/draft/rankings?season=2026", rankings_2026))

    def predict_call():
        payload = draft_router.ModelServingPredictionRequest(
            owner_id=user.id,
            season=2026,
            league_id=user.league_id,
            limit=5,
            model_version="current",
            draft_state=draft_router.ModelServingDraftState(drafted_player_ids=[]),
        )
        response = draft_router.predict_model_recommendations(
            payload=payload,
            db=db,
            current_user=user,
        )
        return f"recommendations={response.recommendation_count}"

    checks.append(_safe_call("api:/draft/model/predict", predict_call))

    def simulation_call():
        payload = draft_router.DraftSimulationRequest(
            perspective_owner_id=user.id,
            iterations=50,
            seed=42,
            teams_count=12,
            roster_size=16,
            target_key_players=10,
        )
        response = draft_router.run_draft_simulation(
            payload=payload,
            db=db,
            current_user=user,
        )
        return f"key_target_probabilities={len(response.get('key_target_probabilities') or [])}"

    checks.append(_safe_call("api:/draft/simulation", simulation_call))

    def advisor_call():
        request = advisor_router.DraftDayQueryRequest(
            owner_id=user.id,
            season=2026,
            league_id=int(user.league_id),
            question="Explain the current recommendation.",
        )
        response = advisor_router.draft_day_query(request=request, db=db)
        return f"headline={response.headline}"

    checks.append(_safe_call("api:/advisor/draft-day/query", advisor_call))

    def player_season_call():
        player = db.query(models.Player).order_by(models.Player.id.asc()).first()
        if not player:
            raise RuntimeError("No players found")
        response = players_router.get_player_season_details(
            player_id=int(player.id),
            season=2025,
            db=db,
        )
        return f"player_id={response.get('player_id')} games={response.get('games_played')}"

    checks.append(_safe_call("api:/players/{id}/season-details", player_season_call))

    return checks


def _endpoint_source_map() -> list[tuple[str, str]]:
    return [
        (
            "/draft/rankings",
            "PostgreSQL: draft_values, players, scoring_rules, draft_picks, keepers, player_weekly_stats",
        ),
        (
            "/draft/model/predict",
            "PostgreSQL: same as /draft/rankings (+ request draft_state payload)",
        ),
        (
            "/advisor/draft-day/query",
            "PostgreSQL: rankings-backed data from /draft/rankings service path",
        ),
        (
            "/players/{id}/season-details",
            "PostgreSQL: players, player_weekly_stats",
        ),
        (
            "/draft/simulation",
            "CSV files: backend/data/draft_results.csv, players.csv, historical_rankings.csv, draft_budget.csv",
        ),
    ]


def build_report() -> tuple[str, list[CheckResult], list[CheckResult]]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    ensure_runtime_schema()

    db = SessionLocal()
    try:
        user = _pick_user(db)
        dataset_results = _dataset_checks(db)
        api_results = _api_checks(db, user)
    finally:
        db.close()

    lines: list[str] = []
    lines.append("# Draft Analyzer API Audit")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Context")
    lines.append("")
    lines.append("- Scope: Draft Day Analyzer data paths")
    lines.append("- Validation mode: direct router invocation with live SQLAlchemy session")
    lines.append("")

    lines.append("## Endpoint Source Map")
    lines.append("")
    lines.append("| Endpoint | Primary Data Source |")
    lines.append("|---|---|")
    for endpoint, source in _endpoint_source_map():
        lines.append(f"| `{endpoint}` | {source} |")
    lines.append("")

    lines.append("## Dataset Health")
    lines.append("")
    lines.append("| Dataset Check | Status | Details |")
    lines.append("|---|---|---|")
    for result in dataset_results:
        lines.append(f"| `{result.name}` | {result.status} | {result.details} |")
    lines.append("")

    lines.append("## API Check Matrix")
    lines.append("")
    lines.append("| API Check | Status | Details |")
    lines.append("|---|---|---|")
    for result in api_results:
        lines.append(f"| `{result.name}` | {result.status} | {result.details} |")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    lines.append("- `WARN` on sparse historical datasets means endpoint may function but output quality may be reduced.")
    lines.append("- `/draft/simulation` health depends on CSV freshness/shape, not only PostgreSQL values.")

    return "\n".join(lines) + "\n", dataset_results, api_results


def main() -> None:
    report, dataset_results, api_results = build_report()
    out_path = Path(__file__).resolve().parents[1] / "docs" / "DRAFT_ANALYZER_API_AUDIT.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"wrote_report={out_path}")
    has_failures = any(item.status == "FAIL" for item in [*dataset_results, *api_results])
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
