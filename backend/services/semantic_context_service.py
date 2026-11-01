from collections.abc import Iterable

from .. import models
from ..schemas.semantic import (
    PointBasis,
    ScoringDefinitionStatus,
    SemanticContext,
    SemanticMembershipContext,
    SemanticPointContext,
    SemanticScope,
)


def build_semantic_point_context(
    *,
    sources: Iterable[str | None],
    value_basis: PointBasis,
    scoring_definition: ScoringDefinitionStatus,
    selection_policy: str,
    value_count: int,
    unknown_value_count: int,
) -> SemanticPointContext:
    source_rows = list(sources)
    source_names = sorted(
        {source.strip() for source in source_rows if source and source.strip()}
    )
    missing_source_count = sum(
        1 for source in source_rows if not source or not source.strip()
    )

    if not source_names:
        source_status = "unknown"
    elif len(source_names) > 1 or missing_source_count:
        source_status = "mixed"
    else:
        source_status = "known"

    if value_count == 0 or unknown_value_count >= value_count:
        value_status = "unknown"
    elif unknown_value_count:
        value_status = "partial"
    else:
        value_status = "known"

    return SemanticPointContext(
        source_status=source_status,
        sources=source_names,
        unknown_source_count=missing_source_count,
        value_basis=value_basis,
        scoring_definition=scoring_definition,
        selection_policy=selection_policy,
        freshness="unknown",
        value_status=value_status,
        value_count=value_count,
        unknown_value_count=unknown_value_count,
    )


def aggregate_semantic_point_contexts(
    contexts: Iterable[SemanticPointContext],
) -> SemanticPointContext:
    context_rows = list(contexts)
    sources = sorted({source for context in context_rows for source in context.sources})
    unknown_source_count = sum(context.unknown_source_count for context in context_rows)
    bases = {context.value_basis for context in context_rows}
    definitions = {context.scoring_definition for context in context_rows}
    value_count = sum(context.value_count for context in context_rows)
    unknown_value_count = sum(context.unknown_value_count for context in context_rows)

    if not sources:
        source_status = "unknown"
    elif len(sources) > 1 or unknown_source_count:
        source_status = "mixed"
    else:
        source_status = "known"

    if value_count == 0 or unknown_value_count >= value_count:
        value_status = "unknown"
    elif unknown_value_count:
        value_status = "partial"
    else:
        value_status = "known"

    return SemanticPointContext(
        source_status=source_status,
        sources=sources,
        unknown_source_count=unknown_source_count,
        value_basis=next(iter(bases)) if len(bases) == 1 else "unknown",
        scoring_definition=next(iter(definitions)) if len(definitions) == 1 else "unknown",
        selection_policy="aggregated_player_values",
        freshness="unknown",
        value_status=value_status,
        value_count=value_count,
        unknown_value_count=unknown_value_count,
    )


def build_matchup_semantic_context(
    *,
    game: models.Matchup,
    season_year: int,
    home_projected_contexts: Iterable[SemanticPointContext],
    away_projected_contexts: Iterable[SemanticPointContext],
) -> SemanticContext:
    stored_scores = build_semantic_point_context(
        sources=[],
        value_basis="unknown",
        scoring_definition="unknown",
        selection_policy="stored_matchup_scores_without_provenance",
        value_count=2,
        unknown_value_count=2,
    )
    return SemanticContext(
        metric="matchup_team_points",
        scope=SemanticScope(
            league_id=game.league_id,
            season=game.season,
            week=game.week,
        ),
        calculation_scope=SemanticScope(
            league_id=game.league_id,
            season=season_year,
            week=game.week,
        ),
        stored_scores=stored_scores,
        home_projected=aggregate_semantic_point_contexts(home_projected_contexts),
        away_projected=aggregate_semantic_point_contexts(away_projected_contexts),
        membership=SemanticMembershipContext(
            basis="current_draft_pick_status",
            league_scoped=False,
            season_scoped=False,
            week_scoped=False,
            historical_status="current_only",
            allows_unscoped_legacy_picks=True,
        ),
    )


def build_player_stat_semantic_context(
    *,
    player_id: int,
    season: int,
    rows: Iterable[models.PlayerWeeklyStat],
    week: int | None = None,
    aggregation: str | None = None,
) -> SemanticContext:
    stat_rows = list(rows)
    unknown_value_count = sum(
        1 for row in stat_rows if row.fantasy_points is None
    )
    point_context = build_semantic_point_context(
        sources=[row.source for row in stat_rows],
        value_basis=(
            "source_reported"
            if (
                stat_rows
                and unknown_value_count == 0
                and all(row.source and row.source.strip() for row in stat_rows)
            )
            else "unknown"
        ),
        scoring_definition="unknown",
        selection_policy="all_available_source_rows",
        value_count=len(stat_rows),
        unknown_value_count=unknown_value_count,
    )
    return SemanticContext(
        metric="source_reported_player_points",
        scope=SemanticScope(player_id=player_id, season=season, week=week),
        aggregation=aggregation,
        points=point_context,
        membership=SemanticMembershipContext(
            basis="not_applicable",
            league_scoped=False,
            season_scoped=False,
            week_scoped=False,
            historical_status="not_applicable",
        ),
    )
