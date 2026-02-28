from sqlalchemy.orm import Session
from .. import models_draft_value as dv_models


def get_projected_auction_value(db: Session, player_id: int, season: int) -> float | None:
    """Return a projected auction value for the given player/season.

    Prefer the aggregated DraftValue table; fall back to the most recent
    platform_projections entry for the season.
    """
    if not player_id or not season:
        return None
    # first try aggregated consensus
    draftval = (
        db.query(dv_models.DraftValue)
        .filter(
            dv_models.DraftValue.player_id == player_id,
            dv_models.DraftValue.season == season,
        )
        .first()
    )
    if draftval and draftval.avg_auction_value is not None:
        return draftval.avg_auction_value

    # fallback to raw projection
    proj = (
        db.query(dv_models.PlatformProjection)
        .filter(
            dv_models.PlatformProjection.player_id == player_id,
            dv_models.PlatformProjection.season == season,
        )
        .order_by(dv_models.PlatformProjection.id.desc())
        .first()
    )
    if proj and proj.auction_value is not None:
        return proj.auction_value
    return None
