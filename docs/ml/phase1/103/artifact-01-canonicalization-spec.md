# Artifact 01: Player Metadata Canonicalization Spec (#103)

## Goal
Create deterministic canonical player metadata for downstream model and analytics jobs.

## Inputs
- Source player metadata table/export with at minimum:
  - `Player_ID`
  - `PlayerName`
  - optional `PositionID`
- Positions reference dataset with at minimum:
  - `PositionID`
  - `Position`
- Alias mapping file:
  - `etl/transform/player_metadata_alias_map.yml`

## Transform Rules
1. Normalize raw names using the shared ETL player-name normalizer.
2. Apply explicit alias overrides from the alias map.
3. Normalize positions (`DST`/`D/ST` -> `DEF`).
4. Build deterministic PositionID mapping, preferring fantasy-active tokens (`QB`, `RB`, `WR`, `TE`, `K`, `DEF`) when duplicate PositionID rows exist.
5. Dedupe by `player_id` using deterministic sort keys before first-row selection.
6. Produce stable sorted output by `player_id`.

## Output Contract
- `player_id` (int)
- `source_name` (str)
- `canonical_name` (str)
- `canonical_name_key` (str)
- `source_position_id` (int | null)
- `canonical_position` (str)

## Determinism Guarantee
Given identical inputs and alias map content, digest and row ordering are expected to be identical across runs.
