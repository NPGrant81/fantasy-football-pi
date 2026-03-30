"""Extract MyFantasyLeague exports into CSV files for migration.

This is the first-pass implementation for issue #257. It focuses on
repeatable extraction with predictable folder output and lightweight
normalization per report type.
"""

from __future__ import annotations

import csv
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from defusedxml import ElementTree as ET

import requests


API_BASE = "https://api.myfantasyleague.com"
DEFAULT_REPORT_TYPES = [
    "league",
    "franchises",
    "players",
    "draftResults",
    "rosters",
    "standings",
    "schedule",
    "transactions",
]

# Owner-provided mappings from issue discovery.
KNOWN_LEAGUE_BY_SEASON: dict[int, str] = {
    2002: "29721",
    2003: "39069",
    2004: "46417",
    2005: "20248",
    2006: "22804",
    2007: "14291",
    2008: "48937",
    2009: "24809",
    2010: "10547",
    2011: "15794",
    2012: "33168",
    2013: "16794",
    2014: "23495",
    2015: "43630",
    2016: "38909",
    2017: "38909",
    2018: "38909",
    2019: "38909",
    2020: "38909",
    2021: "38909",
    2022: "38909",
    2023: "11422",
    2024: "11422",
    2025: "11422",
    2026: "11422",
}


@dataclass
class ExtractSummary:
    requested_seasons: list[int]
    extracted_reports: int
    skipped_missing_league_id: int
    failed_reports: int
    output_root: str
    retry_attempts: int
    throttled_retries: int
    unresolved_failures: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_seasons": self.requested_seasons,
            "extracted_reports": self.extracted_reports,
            "skipped_missing_league_id": self.skipped_missing_league_id,
            "failed_reports": self.failed_reports,
            "output_root": self.output_root,
            "retry_attempts": self.retry_attempts,
            "throttled_retries": self.throttled_retries,
            "unresolved_failures": self.unresolved_failures,
        }


@dataclass
class AdaptiveThrottle:
    min_interval_seconds: float
    base_backoff_seconds: float
    max_backoff_seconds: float
    jitter_seconds: float
    max_retries_per_request: int
    cooldown_after_burst_seconds: float
    burst_threshold: int
    max_retry_after_seconds: float

    consecutive_429: int = 0
    last_request_monotonic: float = 0.0
    total_retries: int = 0
    throttled_retries: int = 0

    def wait_for_slot(self) -> None:
        if self.min_interval_seconds <= 0:
            self.last_request_monotonic = time.monotonic()
            return

        now = time.monotonic()
        elapsed = now - self.last_request_monotonic if self.last_request_monotonic else self.min_interval_seconds
        sleep_for = self.min_interval_seconds - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)
        self.last_request_monotonic = time.monotonic()

    def record_success(self) -> None:
        self.consecutive_429 = 0

    def backoff_seconds(self, *, attempt_index: int, retry_after_header: str | None) -> float:
        retry_after_seconds: float | None = None
        if retry_after_header:
            try:
                retry_after_seconds = float(retry_after_header)
            except (TypeError, ValueError):
                retry_after_seconds = None

        if retry_after_seconds is not None:
            delay = min(max(retry_after_seconds, 0.0), self.max_retry_after_seconds)
        else:
            exp_delay = self.base_backoff_seconds * (2 ** max(attempt_index - 1, 0))
            delay = min(exp_delay, self.max_backoff_seconds)

        if self.jitter_seconds > 0:
            delay += random.uniform(0, self.jitter_seconds)

        if self.consecutive_429 >= self.burst_threshold:
            delay += self.cooldown_after_burst_seconds

        return delay

    def record_retry(self, *, was_throttle: bool) -> None:
        self.total_retries += 1
        if was_throttle:
            self.throttled_retries += 1


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_non_empty(row: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["season", "league_id", "source_system", "source_endpoint", "extracted_at_utc"])
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _meta(season: int, league_id: str, report_type: str, extracted_at: str) -> dict[str, Any]:
    return {
        "season": season,
        "league_id": league_id,
        "source_system": "mfl",
        "source_endpoint": report_type,
        "extracted_at_utc": extracted_at,
    }


def _normalize_league(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    root = payload.get("league") or payload
    row = {
        **_meta(season, league_id, "league", extracted_at),
        "league_name": _first_non_empty(root, ["name", "leagueName"]),
        "franchise_count": len(_as_list(root.get("franchises", {}).get("franchise"))),
        "salary_cap": _first_non_empty(root, ["salaryCapAmount", "salaryCap"]),
        "roster_size": _first_non_empty(root, ["rosterSize", "franchisePlayerLimit"]),
    }
    return [row]


def _normalize_players(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    players = _as_list((payload.get("players") or {}).get("player"))
    for player in players:
        rows.append(
            {
                **_meta(season, league_id, "players", extracted_at),
                "player_mfl_id": _first_non_empty(player, ["id", "player_id"]),
                "player_name": _first_non_empty(player, ["name", "player_name"]),
                "position": _first_non_empty(player, ["position", "pos"]),
                "nfl_team": _first_non_empty(player, ["team", "nfl_team"]),
                "status": _first_non_empty(player, ["status"]),
                "raw_player": json.dumps(player, separators=(",", ":")),
            }
        )
    return rows


def _normalize_franchises(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = payload.get("league") or payload
    franchises = _as_list((root.get("franchises") or {}).get("franchise"))
    for franchise in franchises:
        rows.append(
            {
                **_meta(season, league_id, "franchises", extracted_at),
                "franchise_id": _first_non_empty(franchise, ["id", "franchise_id"]),
                "franchise_name": _first_non_empty(franchise, ["name", "franchise_name"]),
                "owner_name": _first_non_empty(franchise, ["owner_name", "owner", "name"]),
                "owner_email": _first_non_empty(franchise, ["email", "owner_email"]),
                "division": _first_non_empty(franchise, ["division"]),
                "raw_franchise": json.dumps(franchise, separators=(",", ":")),
            }
        )
    return rows


def _normalize_draft_results(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    def _infer_draft_style(*, pick: dict[str, Any], draft_unit: dict[str, Any], source: str) -> str:
        if source == "auctionResults":
            return "auction"

        draft_type = str(_first_non_empty(draft_unit, ["draftType"], "") or "").strip().lower()
        if "auction" in draft_type:
            return "auction"

        # Classic snake drafts expose explicit round/pick sequencing and/or round 1 order.
        if str(_first_non_empty(pick, ["round"], "") or "").strip() or str(_first_non_empty(pick, ["pick", "pickNumber"], "") or "").strip():
            return "snake"
        if str(_first_non_empty(draft_unit, ["round1DraftOrder"], "") or "").strip():
            return "snake"

        # Bid-based fields indicate auction-like semantics when no explicit sequence exists.
        if str(_first_non_empty(pick, ["cost", "amount", "bid", "winningBid"], "") or "").strip():
            return "auction"

        return "unknown"

    def _coerce_pick(pick: dict[str, Any]) -> dict[str, Any]:
        source = str(_first_non_empty(pick, ["source"], "draftResults") or "draftResults")
        return {
            "franchise_id": _first_non_empty(pick, ["franchise", "franchise_id"]),
            "player_mfl_id": _first_non_empty(pick, ["player", "player_id"]),
            "pick_number": _first_non_empty(pick, ["pick", "pickNumber"]),
            "round": _first_non_empty(pick, ["round"]),
            "winning_bid": _first_non_empty(pick, ["cost", "amount", "bid"]),
            "is_keeper_pick": str(_first_non_empty(pick, ["keeper"], "0")).lower() in {"1", "true", "yes"},
            "draft_source": source,
            "draft_style": _infer_draft_style(pick=pick, draft_unit=draft_unit if isinstance(draft_unit, dict) else {}, source=source),
            "raw_pick": json.dumps(pick, separators=(",", ":")),
        }

    def _extract_picks_from_payload_draft_unit(draft_unit: dict[str, Any]) -> list[dict[str, Any]]:
        picks = _as_list(draft_unit.get("draftPick"))
        return [pick for pick in picks if isinstance(pick, dict)]

    def _extract_picks_from_auction_results_payload(auction_payload: dict[str, Any]) -> list[dict[str, Any]]:
        auction_results = auction_payload.get("auctionResults") or {}
        auction_unit = auction_results.get("auctionUnit") if isinstance(auction_results, dict) else {}
        auctions = _as_list((auction_unit or {}).get("auction"))
        picks: list[dict[str, Any]] = []
        for auction in auctions:
            if not isinstance(auction, dict):
                continue
            picks.append(
                {
                    "franchise": auction.get("franchise"),
                    "player": auction.get("player"),
                    "cost": auction.get("winningBid"),
                    "timestamp": auction.get("lastBidTime") or auction.get("timeStarted"),
                    "round": auction.get("round"),
                    "pick": auction.get("pick"),
                    "source": "auctionResults",
                }
            )
        return picks

    def _extract_picks_from_static_url(static_url: str) -> list[dict[str, Any]]:
        try:
            response = requests.get(static_url, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception:  # noqa: BLE001
            return []

        picks: list[dict[str, Any]] = []
        for node in root.findall(".//draftPick"):
            attrs = {key: value for key, value in node.attrib.items()}
            # Preserve element text payload when present in legacy snapshots.
            text_value = (node.text or "").strip()
            if text_value and "comments" not in attrs:
                attrs["comments"] = text_value
            picks.append(attrs)
        return picks

    rows: list[dict[str, Any]] = []
    draft_results = payload.get("draftResults") or {}
    draft_unit = draft_results.get("draftUnit") or {}

    # `draftUnit` can be either a dict (common) or list in older payloads.
    units = _as_list(draft_unit)
    picks: list[dict[str, Any]] = []
    for unit in units:
        if isinstance(unit, dict):
            picks.extend(_extract_picks_from_payload_draft_unit(unit))

    # Some seasons only expose a static XML URL. Fall back when inline picks are absent.
    if not picks and isinstance(draft_unit, dict):
        static_url = str(draft_unit.get("static_url") or "").strip()
        if static_url:
            picks = _extract_picks_from_static_url(static_url)

    # Some auction leagues expose player-linked rows via auctionResults instead.
    auction_payload = payload.get("_auction_results_fallback")
    if (not picks or all(not str((_first_non_empty(pick, ["player", "player_id"]) or "")).strip() for pick in picks)) and isinstance(auction_payload, dict):
        auction_picks = _extract_picks_from_auction_results_payload(auction_payload)
        if auction_picks:
            picks = auction_picks

    for pick in picks:
        normalized_pick = _coerce_pick(pick)
        player_mfl_id = str(normalized_pick.get("player_mfl_id") or "").strip()
        # Import path requires player ids, so skip order-only picks.
        if not player_mfl_id:
            continue

        rows.append(
            {
                **_meta(season, league_id, "draftResults", extracted_at),
                **normalized_pick,
            }
        )
    return rows


def _normalize_rosters(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    franchises = _as_list((payload.get("rosters") or {}).get("franchise"))
    for franchise in franchises:
        franchise_id = _first_non_empty(franchise, ["id", "franchise_id"])
        players = _as_list(franchise.get("player"))
        for player in players:
            if isinstance(player, dict):
                player_id = _first_non_empty(player, ["id", "player_id"])
                roster_status = _first_non_empty(player, ["status", "type"])
            else:
                player_id = player
                roster_status = None

            rows.append(
                {
                    **_meta(season, league_id, "rosters", extracted_at),
                    "franchise_id": franchise_id,
                    "player_mfl_id": player_id,
                    "roster_status": roster_status,
                }
            )
    return rows


def _normalize_standings(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    standings_root = payload.get("standings") or payload.get("leagueStandings") or {}
    franchises = _as_list((standings_root or {}).get("franchise"))
    for franchise in franchises:
        wins = _first_non_empty(franchise, ["w", "wins", "h2hw"], 0)
        losses = _first_non_empty(franchise, ["l", "losses", "h2hl"], 0)
        ties = _first_non_empty(franchise, ["t", "ties", "h2ht"], 0)
        rows.append(
            {
                **_meta(season, league_id, "standings", extracted_at),
                "franchise_id": _first_non_empty(franchise, ["id", "franchise_id"]),
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "points_for": _first_non_empty(franchise, ["pf", "points_for", "totalpf"]),
                "points_against": _first_non_empty(franchise, ["pa", "points_against", "totalpa"]),
                "rank": _first_non_empty(franchise, ["rank", "h2hrank", "overallrank"]),
                "raw_standing": json.dumps(franchise, separators=(",", ":")),
            }
        )
    return rows


def _normalize_schedule(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    schedule_root = payload.get("schedule") or {}
    weeks = _as_list((schedule_root or {}).get("week"))
    if not weeks:
        weeks = _as_list((schedule_root or {}).get("weeklySchedule"))

    for week_row in weeks:
        week = _first_non_empty(week_row, ["week", "id"])
        matchups = _as_list(week_row.get("matchup"))
        for matchup in matchups:
            home_id = _first_non_empty(matchup, ["franchise1", "home"])
            away_id = _first_non_empty(matchup, ["franchise2", "away"])
            home_score = _first_non_empty(matchup, ["score1", "home_score"])
            away_score = _first_non_empty(matchup, ["score2", "away_score"])

            # Modern payload shape: matchup.franchise = [{id,isHome,score,...}, {id,isHome,score,...}]
            if not home_id and not away_id:
                sides = _as_list(matchup.get("franchise"))
                if len(sides) >= 2:
                    home_side = None
                    away_side = None
                    for side in sides:
                        is_home = str(side.get("isHome") or "").strip()
                        if is_home == "1":
                            home_side = side
                        elif is_home == "0":
                            away_side = side
                    if home_side is None:
                        home_side = sides[0]
                    if away_side is None:
                        away_side = sides[1] if len(sides) > 1 else None

                    home_id = _first_non_empty(home_side or {}, ["id", "franchise_id"])
                    away_id = _first_non_empty(away_side or {}, ["id", "franchise_id"])
                    home_score = _first_non_empty(home_side or {}, ["score", "points", "home_score"])
                    away_score = _first_non_empty(away_side or {}, ["score", "points", "away_score"])

            rows.append(
                {
                    **_meta(season, league_id, "schedule", extracted_at),
                    "week": week,
                    "home_franchise_id": home_id,
                    "away_franchise_id": away_id,
                    "home_score": home_score,
                    "away_score": away_score,
                    "raw_matchup": json.dumps(matchup, separators=(",", ":")),
                }
            )
    return rows


def _normalize_transactions(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    txs = _as_list((payload.get("transactions") or {}).get("transaction"))
    for tx in txs:
        tx_id = _first_non_empty(tx, ["id", "transaction_id"])
        tx_type = _first_non_empty(tx, ["type", "transaction_type"])
        timestamp = _first_non_empty(tx, ["timestamp", "processed_at"])

        players = _as_list(tx.get("player"))
        if not players:
            rows.append(
                {
                    **_meta(season, league_id, "transactions", extracted_at),
                    "transaction_id": tx_id,
                    "week": _first_non_empty(tx, ["week"]),
                    "franchise_id": _first_non_empty(tx, ["franchise", "franchise_id"]),
                    "transaction_type": tx_type,
                    "player_mfl_id": None,
                    "amount": _first_non_empty(tx, ["amount", "bid"]),
                    "processed_at": timestamp,
                    "raw_transaction": json.dumps(tx, separators=(",", ":")),
                }
            )
            continue

        for player in players:
            if isinstance(player, dict):
                player_id = _first_non_empty(player, ["id", "player_id"])
                franchise_id = _first_non_empty(
                    player,
                    ["franchise", "franchise_id"],
                    _first_non_empty(tx, ["franchise", "franchise_id"]),
                )
            else:
                player_id = player
                franchise_id = _first_non_empty(tx, ["franchise", "franchise_id"])
            rows.append(
                {
                    **_meta(season, league_id, "transactions", extracted_at),
                    "transaction_id": tx_id,
                    "week": _first_non_empty(tx, ["week"]),
                    "franchise_id": franchise_id,
                    "transaction_type": tx_type,
                    "player_mfl_id": player_id,
                    "amount": _first_non_empty(tx, ["amount", "bid"]),
                    "processed_at": timestamp,
                    "raw_transaction": json.dumps(tx, separators=(",", ":")),
                }
            )
    return rows


NORMALIZERS = {
    "league": _normalize_league,
    "franchises": _normalize_franchises,
    "players": _normalize_players,
    "draftResults": _normalize_draft_results,
    "rosters": _normalize_rosters,
    "standings": _normalize_standings,
    "schedule": _normalize_schedule,
    "transactions": _normalize_transactions,
}


def _fetch_json(
    *,
    season: int,
    league_id: str,
    report_type: str,
    timeout_seconds: int,
    session_cookie: str | None,
    session: requests.Session,
    throttle: AdaptiveThrottle,
) -> dict[str, Any]:
    effective_type = "league" if report_type == "franchises" else report_type
    params = {
        "TYPE": effective_type,
        "JSON": 1,
        "L": league_id,
    }

    headers: dict[str, str] = {}
    if session_cookie:
        headers["Cookie"] = session_cookie

    last_exc: Exception | None = None
    for attempt in range(1, throttle.max_retries_per_request + 2):
        throttle.wait_for_slot()
        try:
            response = session.get(
                f"{API_BASE}/{season}/export",
                params=params,
                headers=headers,
                timeout=timeout_seconds,
            )

            if response.status_code == 429:
                throttle.consecutive_429 += 1
                if attempt > throttle.max_retries_per_request:
                    response.raise_for_status()

                delay = throttle.backoff_seconds(
                    attempt_index=attempt,
                    retry_after_header=response.headers.get("Retry-After"),
                )
                throttle.record_retry(was_throttle=True)
                print(
                    f"[retry] season={season} type={report_type} status=429 "
                    f"attempt={attempt}/{throttle.max_retries_per_request} sleep={delay:.1f}s"
                )
                time.sleep(delay)
                continue

            if 500 <= response.status_code <= 599:
                if attempt > throttle.max_retries_per_request:
                    response.raise_for_status()
                delay = min(throttle.base_backoff_seconds * attempt, throttle.max_backoff_seconds)
                throttle.record_retry(was_throttle=False)
                print(
                    f"[retry] season={season} type={report_type} status={response.status_code} "
                    f"attempt={attempt}/{throttle.max_retries_per_request} sleep={delay:.1f}s"
                )
                time.sleep(delay)
                continue

            response.raise_for_status()
            throttle.record_success()
            return response.json()
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt > throttle.max_retries_per_request:
                break
            delay = min(throttle.base_backoff_seconds * attempt, throttle.max_backoff_seconds)
            throttle.record_retry(was_throttle=False)
            print(
                f"[retry] season={season} type={report_type} network_error={type(exc).__name__} "
                f"attempt={attempt}/{throttle.max_retries_per_request} sleep={delay:.1f}s"
            )
            time.sleep(delay)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"request failed without response for season={season} type={report_type}")


def run_mfl_history_extract(
    *,
    start_year: int,
    end_year: int,
    report_types: list[str] | None = None,
    output_root: str = "exports/history",
    timeout_seconds: int = 20,
    session_cookie: str | None = None,
    max_retries_per_request: int = 6,
    min_interval_seconds: float = 0.35,
    base_backoff_seconds: float = 3.0,
    max_backoff_seconds: float = 90.0,
    jitter_seconds: float = 1.0,
    cooldown_after_burst_seconds: float = 15.0,
    burst_threshold: int = 3,
    max_retry_after_seconds: float = 300.0,
) -> dict[str, Any]:
    output_base = Path(output_root)
    report_types = report_types or DEFAULT_REPORT_TYPES
    seasons = list(range(start_year, end_year + 1))

    extracted_reports = 0
    skipped_missing_league_id = 0
    failed_reports = 0
    unresolved_failures: list[dict[str, Any]] = []

    throttle = AdaptiveThrottle(
        min_interval_seconds=min_interval_seconds,
        base_backoff_seconds=base_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        jitter_seconds=jitter_seconds,
        max_retries_per_request=max_retries_per_request,
        cooldown_after_burst_seconds=cooldown_after_burst_seconds,
        burst_threshold=burst_threshold,
        max_retry_after_seconds=max_retry_after_seconds,
    )

    session = requests.Session()

    for season in seasons:
        league_id = KNOWN_LEAGUE_BY_SEASON.get(season)
        if not league_id:
            print(f"[skip] season={season} no known league id mapping")
            skipped_missing_league_id += 1
            continue

        for report_type in report_types:
            extracted_at = datetime.now(timezone.utc).isoformat()
            try:
                payload = _fetch_json(
                    season=season,
                    league_id=league_id,
                    report_type=report_type,
                    timeout_seconds=timeout_seconds,
                    session_cookie=session_cookie,
                    session=session,
                    throttle=throttle,
                )

                if report_type == "draftResults":
                    try:
                        auction_payload = _fetch_json(
                            season=season,
                            league_id=league_id,
                            report_type="auctionResults",
                            timeout_seconds=timeout_seconds,
                            session_cookie=session_cookie,
                            session=session,
                            throttle=throttle,
                        )
                        if isinstance(auction_payload, dict) and "error" not in auction_payload:
                            payload["_auction_results_fallback"] = auction_payload
                    except Exception:  # noqa: BLE001
                        # Not all seasons/leagues expose auction results.
                        pass

                raw_path = output_base / "raw" / report_type / f"{season}.json"
                _write_json(raw_path, payload)

                normalizer = NORMALIZERS.get(report_type)
                if normalizer is None:
                    rows = [
                        {
                            **_meta(season, league_id, report_type, extracted_at),
                            "payload_json": json.dumps(payload, separators=(",", ":")),
                        }
                    ]
                else:
                    rows = normalizer(payload, season, league_id, extracted_at)

                csv_path = output_base / report_type / f"{season}.csv"
                _write_csv(csv_path, rows)
                print(f"[ok] season={season} type={report_type} rows={len(rows)}")
                extracted_reports += 1
            except Exception as exc:  # noqa: BLE001
                failed_reports += 1
                print(f"[error] season={season} type={report_type} {exc}")
                unresolved_failures.append(
                    {
                        "season": season,
                        "league_id": league_id,
                        "report_type": report_type,
                        "error": str(exc),
                        "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
                if "football7.myfantasyleague.com" in str(exc):
                    print(
                        "[hint] legacy host football7.myfantasyleague.com did not resolve; "
                        "capture this season via manual export/snapshot and import as CSV"
                    )

    session.close()

    summary = ExtractSummary(
        requested_seasons=seasons,
        extracted_reports=extracted_reports,
        skipped_missing_league_id=skipped_missing_league_id,
        failed_reports=failed_reports,
        output_root=str(output_base),
        retry_attempts=throttle.total_retries,
        throttled_retries=throttle.throttled_retries,
        unresolved_failures=len(unresolved_failures),
    )

    summary_path = output_base / "_run_summary.json"
    _write_json(summary_path, summary.to_dict())

    failed_reports_path = output_base / "_failed_reports.json"
    _write_json(
        failed_reports_path,
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "output_root": str(output_base),
            "unresolved_failures": unresolved_failures,
        },
    )

    return summary.to_dict()