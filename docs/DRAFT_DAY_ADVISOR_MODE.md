# Draft Day Advisor Mode (Trigger Pipeline MVP)

This MVP adds event-driven advisor responses for live auction moments with low-latency deterministic templates.

## Endpoints

- `POST /advisor/draft-day/event`
  - Handles event types: `nomination`, `bid_update`, `roster_update`, `user_query`
  - Returns a structured payload for chatbot/UI cards:
    - `message_type` (`recommendation`, `alert`, `explanation`, `comparison`, `strategy_summary`)
    - `headline`, `body`
    - `recommended_bid`, `risk_score`, `bidding_war_likelihood`, `value_tier`
    - `suggested_alternatives`, `alerts`, `quick_actions`
- `POST /advisor/draft-day/query`
  - Convenience route for explicit user query interactions.

## Trigger Logic Included

- Nomination guidance using owner-context rankings
- Bid escalation alert when current bid exceeds owner-safe cap
- Roster strategy summary with proactive alerts
- Compare/explain query handling from chat input

## Proactive Alerts Included

- Position imbalance (RB-heavy or WR-heavy)
- Overspending risk (low dollars-per-slot)
- Position run detection from recent nominations

## Latency and Reliability

- In-memory ranking cache with 15-second TTL per `(season, league_id, owner_id)`
- Template-first responses (no external LLM dependency in event path)
- Safe fallback values when ranking fields are missing

## Intended Frontend Usage

- Emit events from draft board actions (nominate, bid change, roster change)
- Render response cards directly from structured payload
- Wire quick actions (`Compare`, `Simulate`, `Explain`) to `draft-day/query`
