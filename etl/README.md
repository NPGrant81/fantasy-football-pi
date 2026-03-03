# ETL Pipeline for Fantasy Football Draft Value

This directory contains all scripts and documentation for extracting, transforming, and loading draft value and projection data from multiple sources (Yahoo, ESPN, DraftSharks, etc.) into the main PostgreSQL database.

## Structure

- `extract/` — Source-specific scrapers and API clients
- `transform/` — Data normalization, mapping, and cleaning utilities
- `load/` — Scripts to insert/update data in the database

## Manual Player Mapping

- Use a dedicated `manual_player_mappings` table or CSV for edge-case player ID overrides.
- The ETL pipeline will always check this mapping before using automated matching.

## Workflow

1. **Extract:** Download/scrape raw data from each platform. Store raw JSON as needed.
2. **Transform:** Normalize player names, ADP, position rank, and apply manual mappings.
3. **Load:** Insert/update the normalized and aggregated data into the database.

## Historical league ML rankings

To generate player rankings without external ADP dependencies, use historical league draft outcomes:

- Input datasets:
	- `backend/data/draft_results.csv`
	- `backend/data/players.csv`
- Feature engineering includes:
	- multi-year bid averages/medians
	- recent 3-year form
	- bid trend slope
	- position scarcity and consistency boosts
- Output:
	- ranked CSV with predicted auction values and tiers
	- optional load into `DraftValue` table for backend consumption

Run:

```bash
python -m etl.build_historical_rankings --season 2026 --output backend/data/historical_rankings.csv --load-db
```

## Monte Carlo draft simulation

Run full-league auction simulations (12 teams / configurable) and export iteration-level metrics:

```bash
python -m etl.build_monte_carlo_simulation --iterations 1000 --target-owner-id 1 --output-dir backend/data/simulation
```

Outputs include:

- `draft_picks.csv` (per-pick outcomes)
- `team_metrics.csv` (per-iteration team outcomes)
- `owner_summary.csv` (OwnerID-focused aggregate outcomes)
- `assumptions.json` (explicit simulation assumptions)
- `owner_points_distribution.json` (distribution summary for the target owner)

## Dependencies

- Python 3.9+
- pandas, requests, SQLAlchemy, psycopg2-binary, etc. (see requirements.txt)

## Running

- Each stage can be run independently or as a full pipeline.
- See individual scripts for usage instructions.

---

For questions or manual mapping, see the main project documentation and the `manual_player_mappings` table schema.
