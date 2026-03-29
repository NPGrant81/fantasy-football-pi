from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import json
import logging
import os
from typing import Any
from urllib.request import Request, urlopen

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend import models


LOGGER = logging.getLogger(__name__)


@dataclass
class IngestSummary:
	inserted: int
	linked: int
	skipped: int


def parse_iso_datetime(value: str | None) -> datetime | None:
	if not value:
		return None
	try:
		return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
	except ValueError:
		return None


def sentiment_from_text(*, title: str, summary: str | None = None, content: str | None = None) -> tuple[float, str, list[str]]:
	text = " ".join([title or "", summary or "", content or ""]).lower()
	positive_terms = {"healthy", "active", "cleared", "boost", "upgraded", "surge", "breakout"}
	negative_terms = {"out", "injury", "questionable", "doubtful", "limited", "suspended", "tear", "strain"}

	pos = sum(1 for term in positive_terms if term in text)
	neg = sum(1 for term in negative_terms if term in text)

	if pos == 0 and neg == 0:
		return 0.0, "neutral", []

	score = (pos - neg) / max(1, pos + neg)
	label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
	tags: list[str] = []
	if any(term in text for term in {"injury", "out", "questionable", "doubtful", "limited", "tear", "strain"}):
		tags.append("injury")
	if any(term in text for term in {"trade", "traded"}):
		tags.append("trade")
	if any(term in text for term in {"breakout", "surge", "boost", "upgraded"}):
		tags.append("performance")
	return round(float(score), 3), label, tags


def _normalize_external_item(raw: dict[str, Any], *, source: str, league_id: int | None = None) -> dict[str, Any] | None:
	title = str(raw.get("title") or "").strip()
	if not title:
		return None

	source_item_id = str(raw.get("id") or raw.get("guid") or raw.get("url") or title).strip()
	summary = str(raw.get("summary") or raw.get("description") or "").strip() or None
	content = str(raw.get("content") or "").strip() or None
	url = str(raw.get("url") or raw.get("link") or "").strip() or None

	published_at = None
	raw_published = raw.get("published_at") or raw.get("published") or raw.get("timestamp")
	if raw_published:
		published_at = parse_iso_datetime(str(raw_published))

	if published_at is None:
		published_at = datetime.now(timezone.utc)

	score, label, tags = sentiment_from_text(title=title, summary=summary, content=content)

	return {
		"league_id": league_id,
		"source": source,
		"source_item_id": source_item_id,
		"title": title,
		"summary": summary,
		"content": content,
		"url": url,
		"published_at": published_at,
		"sentiment_score": score,
		"sentiment_label": label,
		"sentiment_tags": tags,
		"meta_json": {"raw_source": source},
	}


def load_external_news_items(*, league_id: int | None = None) -> list[dict[str, Any]]:
	urls_raw = os.getenv("PLAYER_NEWS_SOURCE_URLS", "").strip()
	if not urls_raw:
		return []

	timeout_seconds = int(os.getenv("PLAYER_NEWS_SOURCE_TIMEOUT_SECONDS", "8"))
	items: list[dict[str, Any]] = []

	for raw_url in [v.strip() for v in urls_raw.split(",") if v.strip()]:
		request = Request(raw_url, headers={"User-Agent": "ffpi-player-news/1.0"})
		try:
			with urlopen(request, timeout=timeout_seconds) as response:
				payload = json.loads(response.read().decode("utf-8"))
		except Exception as exc:
			LOGGER.warning("player_news.external_fetch_failed", extra={"url": raw_url, "error": str(exc)})
			continue

		raw_items = payload if isinstance(payload, list) else payload.get("items", []) if isinstance(payload, dict) else []
		if not isinstance(raw_items, list):
			continue

		for raw_item in raw_items:
			if not isinstance(raw_item, dict):
				continue
			normalized = _normalize_external_item(raw_item, source="external", league_id=league_id)
			if normalized:
				items.append(normalized)

	return items


def collect_draft_activity_news(db: Session, *, league_id: int, limit: int = 200) -> list[dict[str, Any]]:
	picks = (
		db.query(models.DraftPick)
		.join(models.User, models.DraftPick.owner_id == models.User.id)
		.join(models.Player, models.DraftPick.player_id == models.Player.id)
		.filter(models.DraftPick.league_id == league_id, ~models.User.username.like("hist_%"))
		.order_by(desc(models.DraftPick.id))
		.limit(limit)
		.all()
	)

	items: list[dict[str, Any]] = []
	for pick in picks:
		owner_name = pick.owner.username if pick.owner else "Unknown Owner"
		player_name = pick.player.name if pick.player else "Unknown Player"
		title = f"{owner_name} drafted {player_name} for ${pick.amount}"
		score, label, tags = sentiment_from_text(title=title)

		items.append(
			{
				"league_id": league_id,
				"source": "draft_activity",
				"source_item_id": f"draft_pick:{pick.id}",
				"title": title,
				"summary": None,
				"content": None,
				"url": None,
				"published_at": parse_iso_datetime(pick.timestamp) or datetime.now(timezone.utc),
				"sentiment_score": score,
				"sentiment_label": label,
				"sentiment_tags": tags,
				"meta_json": {"owner_id": pick.owner_id, "player_id": pick.player_id},
			}
		)

	return items


def _candidate_players_for_league(db: Session, *, league_id: int | None) -> list[tuple[int, str, str]]:
	player_rows = (
		db.query(models.Player.id, models.Player.name)
		.join(models.DraftPick, models.DraftPick.player_id == models.Player.id)
		.filter(models.DraftPick.league_id == league_id)
		.distinct()
		.all()
		if league_id is not None
		else db.query(models.Player.id, models.Player.name).all()
	)

	aliases = db.query(models.PlayerAlias.player_id, models.PlayerAlias.alias_name).all()
	alias_map: dict[int, list[str]] = {}
	for pid, alias in aliases:
		if not alias:
			continue
		alias_map.setdefault(pid, []).append(alias)

	candidates: list[tuple[int, str, str]] = []
	for pid, name in player_rows:
		if not name:
			continue
		candidates.append((pid, name, "name_exact"))
		for alias in alias_map.get(pid, []):
			candidates.append((pid, alias, "alias"))
	return candidates


def _link_news_item_to_players(db: Session, item: models.PlayerNewsItem) -> int:
	text_blob = " ".join([item.title or "", item.summary or "", item.content or ""]).lower()
	if not text_blob.strip():
		return 0

	candidates = _candidate_players_for_league(db, league_id=item.league_id)
	links_created = 0
	linked_player_ids: set[int] = set()

	for player_id, candidate_name, reason in candidates:
		normalized = candidate_name.lower().strip()
		if not normalized:
			continue

		confidence = 0.0
		match_reason = ""
		if normalized in text_blob:
			confidence = 1.0 if reason == "name_exact" else 0.9
			match_reason = reason
		else:
			ratio = SequenceMatcher(None, normalized, text_blob).ratio()
			if ratio >= 0.62:
				confidence = min(0.8, ratio)
				match_reason = f"fuzzy:{reason}"

		if confidence < 0.62 or player_id in linked_player_ids:
			continue

		linked_player_ids.add(player_id)
		db.add(
			models.PlayerNewsLink(
				news_item_id=item.id,
				player_id=player_id,
				confidence=round(confidence, 3),
				match_reason=match_reason,
			)
		)
		links_created += 1

	return links_created


def ingest_news_items(db: Session, *, items: list[dict[str, Any]]) -> IngestSummary:
	inserted = 0
	skipped = 0
	linked = 0

	for raw in items:
		source = str(raw.get("source") or "internal")
		source_item_id = str(raw.get("source_item_id") or "").strip()
		if not source_item_id:
			skipped += 1
			continue

		existing = (
			db.query(models.PlayerNewsItem)
			.filter(
				models.PlayerNewsItem.source == source,
				models.PlayerNewsItem.source_item_id == source_item_id,
			)
			.first()
		)
		if existing:
			skipped += 1
			continue

		item = models.PlayerNewsItem(
			league_id=raw.get("league_id"),
			source=source,
			source_item_id=source_item_id,
			title=str(raw.get("title") or "").strip(),
			summary=raw.get("summary"),
			content=raw.get("content"),
			url=raw.get("url"),
			published_at=raw.get("published_at"),
			sentiment_score=float(raw.get("sentiment_score") or 0.0),
			sentiment_label=str(raw.get("sentiment_label") or "neutral"),
			sentiment_tags=list(raw.get("sentiment_tags") or []),
			meta_json=raw.get("meta_json"),
		)
		db.add(item)
		db.flush()

		linked += _link_news_item_to_players(db, item)
		inserted += 1

	db.commit()
	return IngestSummary(inserted=inserted, linked=linked, skipped=skipped)


def run_ingest_for_league(
	db: Session,
	*,
	league_id: int,
	include_draft_activity: bool = True,
	include_external_sources: bool = True,
) -> IngestSummary:
	items: list[dict[str, Any]] = []
	if include_draft_activity:
		items.extend(collect_draft_activity_news(db, league_id=league_id))
	if include_external_sources:
		items.extend(load_external_news_items(league_id=league_id))

	summary = ingest_news_items(db, items=items)
	rebuild_sentiment_trends(db, league_id=league_id)
	return summary


def _parse_since_or_raise(value: str | None) -> datetime | None:
	if value is None:
		return None
	parsed = parse_iso_datetime(value)
	if parsed is None:
		raise ValueError("Invalid since timestamp. Use ISO-8601 format.")
	return parsed


def get_global_news(
	db: Session,
	*,
	league_id: int | None,
	player_id: int | None,
	since: str | None,
	limit: int,
) -> list[models.PlayerNewsItem]:
	since_dt = _parse_since_or_raise(since)
	query = db.query(models.PlayerNewsItem)
	if league_id is not None:
		query = query.filter(models.PlayerNewsItem.league_id == league_id)
	if since_dt is not None:
		query = query.filter(models.PlayerNewsItem.published_at >= since_dt)
	if player_id is not None:
		query = query.join(models.PlayerNewsLink, models.PlayerNewsLink.news_item_id == models.PlayerNewsItem.id).filter(
			models.PlayerNewsLink.player_id == player_id
		)

	return query.order_by(desc(models.PlayerNewsItem.published_at), desc(models.PlayerNewsItem.id)).limit(limit).all()


def get_team_news(
	db: Session,
	*,
	team_id: int,
	league_id: int | None,
	since: str | None,
	limit: int,
) -> list[models.PlayerNewsItem]:
	since_dt = _parse_since_or_raise(since)
	owner = db.query(models.User).filter(models.User.id == team_id).first()
	if owner is None:
		return []

	resolved_league_id = league_id if league_id is not None else owner.league_id
	if resolved_league_id is None:
		return []

	roster_player_ids = {
		row[0]
		for row in db.query(models.DraftPick.player_id)
		.filter(models.DraftPick.owner_id == team_id, models.DraftPick.league_id == resolved_league_id)
		.distinct()
		.all()
		if row[0] is not None
	}
	if not roster_player_ids:
		return []

	query = (
		db.query(models.PlayerNewsItem)
		.join(models.PlayerNewsLink, models.PlayerNewsLink.news_item_id == models.PlayerNewsItem.id)
		.filter(
			models.PlayerNewsItem.league_id == resolved_league_id,
			models.PlayerNewsLink.player_id.in_(sorted(roster_player_ids)),
		)
	)
	if since_dt is not None:
		query = query.filter(models.PlayerNewsItem.published_at >= since_dt)

	return query.order_by(desc(models.PlayerNewsItem.published_at), desc(models.PlayerNewsItem.id)).limit(limit).all()


def rebuild_sentiment_trends(
	db: Session,
	*,
	league_id: int,
	windows_hours: tuple[int, ...] = (24, 72, 168),
) -> int:
	now = datetime.now(timezone.utc)
	updated = 0

	player_ids = {
		row[0]
		for row in db.query(models.PlayerNewsLink.player_id)
		.join(models.PlayerNewsItem, models.PlayerNewsItem.id == models.PlayerNewsLink.news_item_id)
		.filter(models.PlayerNewsItem.league_id == league_id)
		.distinct()
		.all()
		if row[0] is not None
	}

	for player_id in player_ids:
		for window in windows_hours:
			start = now - timedelta(hours=window)
			rows = (
				db.query(models.PlayerNewsItem.sentiment_score)
				.join(models.PlayerNewsLink, models.PlayerNewsLink.news_item_id == models.PlayerNewsItem.id)
				.filter(
					models.PlayerNewsItem.league_id == league_id,
					models.PlayerNewsLink.player_id == player_id,
					models.PlayerNewsItem.published_at >= start,
				)
				.all()
			)
			scores = [float(row[0]) for row in rows]
			mention_count = len(scores)
			average = round(sum(scores) / mention_count, 3) if mention_count else 0.0

			trend = (
				db.query(models.PlayerNewsSentimentTrend)
				.filter(
					models.PlayerNewsSentimentTrend.league_id == league_id,
					models.PlayerNewsSentimentTrend.player_id == player_id,
					models.PlayerNewsSentimentTrend.window_hours == window,
				)
				.first()
			)
			if trend is None:
				trend = models.PlayerNewsSentimentTrend(
					league_id=league_id,
					player_id=player_id,
					window_hours=window,
					average_score=average,
					mention_count=mention_count,
				)
				db.add(trend)
			else:
				trend.average_score = average
				trend.mention_count = mention_count
			updated += 1

	db.commit()
	return updated


def get_sentiment_trends(
	db: Session,
	*,
	league_id: int,
	player_id: int | None = None,
	window_hours: int | None = None,
) -> list[models.PlayerNewsSentimentTrend]:
	query = db.query(models.PlayerNewsSentimentTrend).filter(models.PlayerNewsSentimentTrend.league_id == league_id)
	if player_id is not None:
		query = query.filter(models.PlayerNewsSentimentTrend.player_id == player_id)
	if window_hours is not None:
		query = query.filter(models.PlayerNewsSentimentTrend.window_hours == window_hours)
	return query.order_by(models.PlayerNewsSentimentTrend.player_id, models.PlayerNewsSentimentTrend.window_hours).all()


def get_significant_sentiment_shifts(
	db: Session,
	*,
	league_id: int,
	min_delta: float = 0.35,
) -> list[dict[str, Any]]:
	trends = get_sentiment_trends(db, league_id=league_id)
	grouped: dict[int, dict[int, models.PlayerNewsSentimentTrend]] = {}
	for trend in trends:
		grouped.setdefault(trend.player_id, {})[trend.window_hours] = trend

	shifts: list[dict[str, Any]] = []
	for player_id, windows in grouped.items():
		short = windows.get(24)
		long = windows.get(168)
		if not short or not long:
			continue
		delta = round(float(short.average_score) - float(long.average_score), 3)
		if abs(delta) < min_delta:
			continue
		player = db.query(models.Player).filter(models.Player.id == player_id).first()
		shifts.append(
			{
				"player_id": player_id,
				"player_name": player.name if player else f"Player {player_id}",
				"short_window_hours": 24,
				"long_window_hours": 168,
				"short_average": float(short.average_score),
				"long_average": float(long.average_score),
				"delta": delta,
				"direction": "up" if delta > 0 else "down",
			}
		)

	shifts.sort(key=lambda row: abs(row["delta"]), reverse=True)
	return shifts
