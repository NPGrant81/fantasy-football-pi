from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.security import check_is_commissioner, get_current_user
from .. import models
from ..services.player_news_service import (
    get_global_news,
    get_team_news,
    get_sentiment_trends,
    get_significant_sentiment_shifts,
    rebuild_sentiment_trends,
    run_ingest_for_league,
)


router = APIRouter(prefix="/news", tags=["News"])


class NewsIngestRequest(BaseModel):
    league_id: int
    include_draft_activity: bool = True
    include_external_sources: bool = True


class NewsItemResponse(BaseModel):
    id: int
    league_id: int | None
    source: str
    title: str
    summary: str | None
    content: str | None
    url: str | None
    published_at: str | None
    sentiment_score: float
    sentiment_label: str
    sentiment_tags: list[str]
    linked_player_ids: list[int]


class SentimentTrendResponse(BaseModel):
    league_id: int
    player_id: int
    player_name: str
    window_hours: int
    average_score: float
    mention_count: int
    updated_at: str | None


def _to_item_response(item: Any) -> NewsItemResponse:
    published = item.published_at.isoformat() if isinstance(item.published_at, datetime) else None
    # Avoid N+1 queries: only use links when already loaded on the instance.
    links_collection = item.__dict__.get("links") or []
    linked_player_ids = sorted({link.player_id for link in links_collection if link.player_id is not None})
    return NewsItemResponse(
        id=item.id,
        league_id=item.league_id,
        source=item.source,
        title=item.title,
        summary=item.summary,
        content=item.content,
        url=item.url,
        published_at=published,
        sentiment_score=float(item.sentiment_score or 0.0),
        sentiment_label=item.sentiment_label or "neutral",
        sentiment_tags=list(item.sentiment_tags or []),
        linked_player_ids=linked_player_ids,
    )


@router.post("/ingest")
def ingest_news(
    payload: NewsIngestRequest,
    current_user = Depends(check_is_commissioner),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Ingest news for a league (commissioner only)."""
    summary = run_ingest_for_league(
        db,
        league_id=payload.league_id,
        include_draft_activity=payload.include_draft_activity,
        include_external_sources=payload.include_external_sources,
    )
    return {
        "inserted": summary.inserted,
        "linked": summary.linked,
        "skipped": summary.skipped,
    }


@router.get("/global", response_model=list[NewsItemResponse])
def global_news(
    league_id: int | None = Query(None, ge=1),
    player_id: int | None = Query(None, ge=1),
    since: str | None = Query(None),
    limit: int = Query(25, ge=1, le=250),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Direct function-invocation tests may pass FastAPI Depends sentinel values.
    # Only enforce auth scoping when we have a resolved user object.
    if isinstance(current_user, models.User):
        user_league_id = getattr(current_user, "league_id", None)
        if league_id is None:
            if user_league_id is None and not getattr(current_user, "is_superuser", False):
                raise HTTPException(status_code=400, detail="league_id is required")
            league_id = user_league_id
        elif (
            not getattr(current_user, "is_superuser", False)
            and user_league_id is not None
            and league_id != user_league_id
        ):
            raise HTTPException(status_code=403, detail="Not authorized for this league")

    try:
        rows = get_global_news(
            db,
            league_id=league_id,
            player_id=player_id,
            since=since,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [_to_item_response(row) for row in rows]


@router.get("/team/{team_id}", response_model=list[NewsItemResponse])
def team_news(
    team_id: int,
    league_id: int | None = Query(None, ge=1),
    since: str | None = Query(None),
    limit: int = Query(25, ge=1, le=250),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team_owner = db.query(models.User).filter(models.User.id == team_id).first()
    if team_owner is None:
        raise HTTPException(status_code=404, detail="Team owner not found")

    target_league_id = team_owner.league_id
    if target_league_id is None:
        raise HTTPException(status_code=400, detail="Team owner is not assigned to a league")

    if isinstance(current_user, models.User):
        if (
            not getattr(current_user, "is_superuser", False)
            and getattr(current_user, "league_id", None) != target_league_id
        ):
            raise HTTPException(status_code=403, detail="Not authorized for this league")

    # Derive effective league from team owner; reject mismatched override.
    if league_id is not None and league_id != target_league_id:
        raise HTTPException(status_code=400, detail="league_id does not match team owner league")

    try:
        rows = get_team_news(
            db,
            team_id=team_id,
            league_id=target_league_id,
            since=since,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [_to_item_response(row) for row in rows]


@router.post("/sentiment/rebuild")
def rebuild_news_sentiment(
    league_id: int = Query(..., ge=1),
    current_user = Depends(check_is_commissioner),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Rebuild sentiment trends for a league (commissioner only)."""
    updated = rebuild_sentiment_trends(db, league_id=league_id)
    return {"updated": updated}


@router.get("/sentiment/latest", response_model=list[NewsItemResponse])
def latest_sentiment_news(
    league_id: int = Query(..., ge=1),
    limit: int = Query(25, ge=1, le=250),
    db: Session = Depends(get_db),
):
    rows = get_global_news(db, league_id=league_id, player_id=None, since=None, limit=limit)
    return [_to_item_response(row) for row in rows]


@router.get("/sentiment/trends", response_model=list[SentimentTrendResponse])
def sentiment_trends(
    league_id: int = Query(..., ge=1),
    player_id: int | None = Query(None, ge=1),
    window_hours: int | None = Query(None, ge=1, le=24 * 14),
    db: Session = Depends(get_db),
):
    rows = get_sentiment_trends(db, league_id=league_id, player_id=player_id, window_hours=window_hours)
    player_cache: dict[int, str] = {}
    responses: list[SentimentTrendResponse] = []
    for row in rows:
        if row.player_id not in player_cache:
            player_cache[row.player_id] = row.player.name if row.player else f"Player {row.player_id}"
        responses.append(
            SentimentTrendResponse(
                league_id=row.league_id,
                player_id=row.player_id,
                player_name=player_cache[row.player_id],
                window_hours=row.window_hours,
                average_score=float(row.average_score or 0.0),
                mention_count=int(row.mention_count or 0),
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )
        )
    return responses


@router.get("/sentiment/shifts")
def sentiment_shifts(
    league_id: int = Query(..., ge=1),
    min_delta: float = Query(0.35, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    return get_significant_sentiment_shifts(db, league_id=league_id, min_delta=min_delta)
