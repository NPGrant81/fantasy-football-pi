from __future__ import annotations


PRIMARY_SCOREBOARD_SOURCE = "espn_scoreboard_primary"
PRIMARY_SUMMARY_SOURCE = "espn_summary_primary"
PRIMARY_PLAY_BY_PLAY_SOURCE = "espn_play_by_play_primary"


def build_primary_scoreboard_url(year: int, week: int | None = None) -> str:
    if week is None:
        return (
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            f"?limit=1000&dates={year}"
        )
    return (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?limit=1000&dates={year}&seasontype=2&week={week}"
    )


def build_failover_scoreboard_urls(year: int, week: int | None = None) -> list[str]:
    if week is None:
        return [f"https://cdn.espn.com/core/nfl/scoreboard?xhr=1&year={year}"]
    return [
        f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={year}&week={week}",
        f"https://cdn.espn.com/core/nfl/scoreboard?xhr=1&year={year}",
    ]


def scoreboard_candidate_urls(
    year: int,
    week: int | None,
    *,
    override_url: str | None = None,
    enable_failover: bool = True,
) -> list[str]:
    urls: list[str] = []
    if override_url:
        urls.append(override_url)

    urls.append(build_primary_scoreboard_url(year, week))
    if enable_failover:
        urls.extend(build_failover_scoreboard_urls(year, week))

    # Keep stable order while removing accidental duplicates.
    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def build_summary_url(event_id: str) -> str:
    return (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
        f"?event={event_id}"
    )


def build_play_by_play_url(event_id: str) -> str:
    return f"https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={event_id}"

