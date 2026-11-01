# Semantic Data Contract

Status: Initial contract; current-source mapping is tracked in [#547](https://github.com/NPGrant81/fantasy-football-pi/issues/547).
Owner: data
Related issues: [#540](https://github.com/NPGrant81/fantasy-football-pi/issues/540), [#548](https://github.com/NPGrant81/fantasy-football-pi/issues/548)

## Purpose and authority

This document defines shared meanings for entities, time context, metrics,
provenance, and freshness across backend, API, ingestion, and analytics
consumers. It is a semantic contract, not a physical schema, provider adapter,
or migration plan.

Use [the data dictionary](data-dictionary.md) for documented legacy and
persisted field shapes, and [the architecture guide](ARCHITECTURE.md) for
layer boundaries and API naming. When existing data cannot establish a
semantic value, consumers must preserve that uncertainty instead of inferring
one.

The terms **MUST**, **MUST NOT**, and **SHOULD** below describe contract
requirements for new or updated consumers. They do not claim that every
existing row or API currently satisfies them; current-source coverage and gaps
are recorded in #547.

## Canonical concepts and keys

| Concept | Canonical key/context | Meaning and boundary |
|---|---|---|
| Player | `player_id` | The application's stable player identifier. Names, positions, and NFL teams are descriptive attributes, not identity keys. |
| Provider player identity | `provider` + `provider_player_id` | An identifier in one provider's namespace. It MUST NOT be compared to another provider's ID without an explicit, evidenced mapping. |
| League | `league_id` | The application's league identifier. A provider league ID is separately namespaced and may change by season. |
| Owner/manager account | `owner_id` | The application's user/account identifier when a league record refers to an owner. It MUST NOT be assumed to be the same as a provider franchise ID or a display name. |
| Season | `season` | The integer calendar year identifying the fantasy/NFL season. A season is not the date on which a record was imported or calculated. |
| Week | `week` | A week within a season. A week number is not globally unique and MUST be qualified by its season and, for league results, its league. |
| Scoring definition | `league_id` + `season` + effective scoring definition | The rules used to interpret fantasy points. A mutable current ruleset is not, by itself, the scoring definition for a historical result. |

Where an external contract uses `year` or `season_year`, it may be normalized to
`season` only after confirming that the source field means the season year.
Field names alone do not prove equivalent semantics.

Provider IDs and app IDs are distinct even when their values happen to match.
Names and aliases can assist resolution but MUST NOT establish identity without
a source-scoped mapping. A low-confidence, ambiguous, or unresolved mapping
remains unresolved; consumers MUST NOT silently select a candidate.

The application currently models `players.id`, `leagues.id`, and `users.id` as
local keys. `Player` currently has `gsis_id` and `espn_id`; native MFL and
Sleeper player identifiers are tracked separately in [#526](https://github.com/NPGrant81/fantasy-football-pi/issues/526).
This contract does not presume that provider IDs or mappings are complete.

## League, season, week, and membership context

League-scoped results MUST carry `league_id`. Season-scoped results MUST carry
`season`; weekly results MUST carry both `season` and `week`. A matchup or
other league result MUST also identify its league. Playoff/regular-season
status is a separate dimension and MUST NOT be inferred from the week number.

`League.current_season` describes the currently active season. It MUST NOT
replace a row's historical `season` or be used to assign a season to a record
whose season is unknown.

The contract distinguishes two kinds of membership:

1. **League account membership**: an account's participation in a league for a
   given period or season.
2. **Roster ownership**: a player's association with an owner in a league and
   season, optionally at a week or effective event/time.

Current membership and historical membership are different facts. A current
association MUST NOT be projected backward to claim historical membership.
Historical membership MUST be tied to the relevant league and season and, when
available, an effective interval or transaction/event.

`PlayerSeason` describes a player's NFL team/position context for a season; it
is not fantasy-league roster membership. A draft record, a current roster
status, and a transaction history record are not interchangeable with a
complete ownership timeline. Existing rows MUST NOT be treated as a complete
historical roster ledger unless the source and coverage establish that fact.

Historical placeholder accounts are not human league members. Existing
database guidance requires member-list queries to exclude `hist_%` usernames;
that prefix is a compatibility safeguard, not the long-term semantic
definition. Use the explicit classification work in [#527](https://github.com/NPGrant81/fantasy-football-pi/issues/527)
when it is implemented and its records are classified. Do not remove the
existing exclusion based on this document.

The exact persisted sources and effective-time rules for these membership
concepts remain to be mapped in #547, coordinating with [#523](https://github.com/NPGrant81/fantasy-football-pi/issues/523).

## Metric meaning, context, and grain

Every shared metric MUST have a stable semantic name and document:

- the subject/entity it measures;
- its grain (the dimensions identifying one observation);
- its unit and aggregation meaning;
- required league, season, week, membership, and scoring context;
- whether it is source-reported or calculated; and
- the definition/version used to produce it, where applicable.

Examples of distinct grains include:

| Metric family | Minimum semantic grain |
|---|---|
| Player weekly statistics | `player_id` + `season` + `week` + source |
| League-scored player points | `player_id` + `league_id` + `season` + `week` + scoring definition |
| Matchup result | `league_id` + `season` + `week` + matchup/participant identity + scoring definition |
| Season aggregate | Subject identity + `season`, plus `league_id` and scoring definition when league rules affect the value |

The label `fantasy_points` alone does not establish scoring semantics. Consumers
MUST distinguish at least:

- **Source-reported points**: a value supplied by a provider, with the source
  and provider scoring basis recorded when known.
- **League-calculated points**: a value calculated under a league's scoring
  rules, with `league_id`, `season`, and the exact rules applied recorded or
  reproducibly identifiable.
- **Unknown-basis points**: an existing value whose source or scoring basis
  cannot be established. It MUST NOT be relabeled as league-calculated or
  compared as if it used a known ruleset.

Scoring context MUST represent the rules effective for the result, not simply
the league's currently active rules. A reproducible calculated result requires
an immutable ruleset/version reference or equivalent evidence of the exact
rules applied. Current rule rows and change logs may inform that evidence but
do not automatically provide a stable version identifier for every stored
result. If the applied rules cannot be established, the scoring basis is
unknown.

Zero is a measured numeric value. It MUST NOT stand for missing, unavailable,
not yet calculated, or unobserved data. `null`, an explicit no-data state, and
an unknown value have different meanings and MUST remain distinguishable.

## Provenance and freshness

Provenance identifies where a value came from and how it was produced.
Consumers SHOULD preserve the following fields when applicable:

| Provenance element | Meaning |
|---|---|
| Source system and source record/key | Originating provider or internal source and its namespaced identity |
| Scope | League, season, week, and entity scope of the observation |
| Observed/as-of time | When the source data was observed, distinct from when the application stored it |
| Transformation version | Version of normalization or ingestion logic |
| Calculation version/context | Metric definition and scoring ruleset used to derive a value |
| Run/record evidence | Ingestion run, source file, fingerprint, or equivalent traceability reference, when available |

Source provenance, transformation history, and calculation context are
separate. A database `created_at` value alone MUST NOT be presented as the
source observation time or proof that data is current. Legacy timestamps whose
timezone or meaning is unclear MUST remain unknown rather than being silently
reinterpreted.

Freshness is a conclusion derived from an observation time and an explicit
source-specific freshness policy; it is not a property implied by a recent
database write. Use these meanings in shared contracts:

| State | Meaning |
|---|---|
| `fresh` | A successful observation is within the declared freshness policy. |
| `stale` | A trustworthy observation exists but is older than that policy. |
| `unknown` | Observation time, successful coverage, or the applicable policy is insufficient to determine freshness. |
| `unavailable` | A source could not be observed for the requested operation; any returned cached value must separately retain its own freshness state. |
| `not_applicable` | Freshness does not apply to this value, such as a static definition. |

`no_data` is different from `unknown`: it means a complete, successful
observation of the requested scope found no matching data. A failed, partial,
or unverified fetch MUST NOT be represented as `no_data`. Source-specific
freshness policies and degradation behavior remain in the adapter and
reliability workstreams, including [#398](https://github.com/NPGrant81/fantasy-football-pi/issues/398)
and [#400](https://github.com/NPGrant81/fantasy-football-pi/issues/400).

Existing provenance varies by data flow. For example, weekly player stats have
a `source`, while MFL ingestion records and normalized HTML facts carry
additional run, file, fingerprint, and normalization details. These examples
are not a claim that all flows expose complete provenance or freshness.

## Compatibility and change boundaries

- This contract introduces no database columns, migrations, data rewrites, or
  API response changes.
- Existing persisted values MUST NOT be reinterpreted solely to make them fit
  these definitions. Unverified values remain unknown or provisional.
- Existing provider adapters and league-settings propagation remain in
  [#398](https://github.com/NPGrant81/fantasy-football-pi/issues/398) and
  [#399](https://github.com/NPGrant81/fantasy-football-pi/issues/399);
  historical data-model hardening remains in #523; canonical player metadata
  work remains in [#361](https://github.com/NPGrant81/fantasy-football-pi/issues/361).
- The source-to-concept mapping and consumer selection are the next phase,
  #547. Consumer adoption and contract tests are tracked in [#549](https://github.com/NPGrant81/fantasy-football-pi/issues/549).
- Any later schema or data migration requires a separate compatibility plan
  covering existing rows, rollout, validation, and rollback. This document is
  not authorization to migrate or reinterpret production data.
