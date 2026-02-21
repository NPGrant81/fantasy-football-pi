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

## Dependencies
- Python 3.9+
- pandas, requests, SQLAlchemy, psycopg2-binary, etc. (see requirements.txt)

## Running
- Each stage can be run independently or as a full pipeline.
- See individual scripts for usage instructions.

---

For questions or manual mapping, see the main project documentation and the `manual_player_mappings` table schema.