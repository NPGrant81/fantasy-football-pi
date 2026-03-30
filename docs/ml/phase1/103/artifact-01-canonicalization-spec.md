# Artifact 01: Player Metadata Canonicalization Spec (#103)

## Goal
Create deterministic canonical player metadata for downstream model and analytics jobs.

## Inputs
- Source player metadata table/export with at minimum:
  - `player_id`
  - `player_name`
  - `position`
  - optional `nfl_team`
- Alias mapping file:
  - `etl/transform/player_metadata_alias_map.yml`

## Transform Rules
1. Normalize raw names using the shared normalizer (`normalize_player_name`).
2. Apply explicit alias overrides from the alias map.
3. Normalize positions (`DST`/`D/ST` -> `DEF`).
4. Dedupe by `player_id` with deterministic tiebreak:
   - highest completeness
   - then canonical_name ascending
5. Produce stable sorted output by (`canonical_name`, `player_id`).

## Output Contract
- `player_id` (int)
- `canonical_name` (str)
- `normalized_name` (str)
- `position` (str)
- `nfl_team` (str)

## Determinism Guarantee
Given identical inputs and alias map content, digest and row ordering are expected to be identical across runs.
