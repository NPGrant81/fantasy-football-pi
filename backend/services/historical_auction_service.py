"""Historical observation readers; these records never imply roster ownership."""

from sqlalchemy.orm import Session, joinedload

from backend import models
from backend.services.player_service import normalize_display_name


def observation_seasons(db: Session, league_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(models.HistoricalAuctionObservation.season)
        .filter(models.HistoricalAuctionObservation.league_id == league_id)
        .distinct()
        .all()
    ]


def historical_auction_events(db: Session, league_id: int, season: int) -> list[dict]:
    rows = (
        db.query(models.HistoricalAuctionObservation)
        .options(joinedload(models.HistoricalAuctionObservation.player))
        .filter(
            models.HistoricalAuctionObservation.league_id == league_id,
            models.HistoricalAuctionObservation.season == season,
        )
        .order_by(models.HistoricalAuctionObservation.source_event_id)
        .all()
    )
    return [
        {
            "id": f"observation-{row.id}",
            "owner_id": row.owner_id,
            "player_id": row.player_id,
            "player_name": normalize_display_name(row.player.name),
            "position": row.position,
            "amount": (
                int(row.winning_bid)
                if row.winning_bid == row.winning_bid.to_integral_value()
                else format(row.winning_bid, "f").rstrip("0").rstrip(".")
            ),
            "timestamp": None,
            "is_keeper": False,
            "source": row.source,
            "source_event_id": row.source_event_id,
            "event_grain": "historical_auction_observation",
            "chronology_established": False,
            "snapshot_nfl_team": row.nfl_team,
            "snapshot_team_labels": row.team_labels,
            "team_basis": row.provenance["event"]["attributes"]["team_basis"],
            "source_timestamp": row.provenance["event"].get("raw_timestamp"),
            "owner_label": f"MFL franchise {row.franchise_id}",
        }
        for row in rows
    ]
