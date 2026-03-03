# UX Insights Spec (Issue 110)

## Purpose

This spec defines how model-serving outputs are presented as actionable draft intelligence inside the Draft Analyzer.

Primary objective: convert raw model numbers into decisions (`bid`, `pass`, `pivot`) with clear tradeoff and risk context.

## Insight Vocabulary

| Term | Source | User Meaning | Visual |
|---|---|---|---|
| `ValueScore` | `recommendations[].value_score` | Relative player value in this context | Numeric + tier tone |
| `ValueTier` | `recommendations[].tier` | Quick value classification | S/A/B/C/D badge tone |
| `RecommendedBid` | `recommendations[].recommended_bid` | Suggested max bid now | Prominent currency value |
| `ConfidenceBand` | Derived from risk (`recommended_bid ± spread`) | Uncertainty range around recommended bid | Min-max range text |
| `RiskScore` | `recommendations[].risk_score` | Volatility / downside risk level | Low/Moderate/High label |
| `Scarcity` | `flags` + demand/availability ratio | How hard replacement will be later | Progress bar |
| `BargainFlag` | Current bid vs predicted/recommended | Bargain / Fair / Overpriced callout | One-line verdict |
| `StrategyAlignment` | Composite of bid discipline + budget + balance | Whether action supports plan | 0–100 score |
| `BiddingPressure` | Current bid vs recommended bid | Auction heat right now | Pressure bar |
| `InflationIndex` | Recent realized / predicted ratio | Market inflation/deflation trend | x-multiple + trend label |

## Thresholds and Rules

### Value tier tone
- `S`: emerald
- `A`: cyan
- `B`: blue
- `C`: amber
- `D`: rose

### Risk labels
- `Low`: `< 45`
- `Moderate`: `45–69`
- `High`: `>= 70`

### Confidence
- `confidence = 100 - risk_score`, clamped to `[5, 95]`
- `band spread = 0.08 + (risk_score / 250)`
- `band = recommended_bid * (1 ± spread)`

### Bargain / Overpriced
- Bargain if `current_bid <= predicted_value * 0.90`
- Overpriced if `current_bid > recommended_bid * 1.10`
- Otherwise Fair market

### Strategy break alert
- Per-position max spend share (owner plan heuristic):
  - QB 15%, RB 32%, WR 32%, TE 12%, DEF 5%, K 4%
- Alert when `current_pos_spend + recommended_bid > position_cap_budget`

## UI Surfaces

## 1) Player Card (ML Insights)
Contains:
- Recommended bid
- Confidence band
- Value score + tier
- Risk label and numeric risk
- Bargain/overpriced signal
- Scarcity and pressure context

Wireframe:

```text
+------------------------------------------------------+
| Player-Level Insights                                |
| Player Name                                          |
| Recommended Bid: $42.00     Confidence: 71%          |
| ValueScore: 47.8             Tier: A                 |
| Confidence Band: $35.20 - $48.90                     |
| Bidding Pressure: [########---] 82% of recommendation|
| BargainFlag: Fair market range                       |
| Risk: Moderate (29.0)                                |
+------------------------------------------------------+
```

## 2) OwnerID=1 Strategy Panel
Contains:
- Budget vs league average
- Aggressiveness index
- Positional balance delta vs league
- Strategy alignment score
- Strategy break alerts

Wireframe:

```text
+------------------------------------------------------+
| Owner Strategy (OwnerID=1)                           |
| Budget vs League: $91 / $104                         |
| Aggressiveness: Balanced   StrategyAlignment: 78     |
| Positional Balance: WR -1.4 vs league                |
| Budget impact: If won at $42 => $49 left             |
| ALERT: Bid exceeds RB max spend plan                 |
+------------------------------------------------------+
```

## 3) Draft Dynamics Sidebar
Contains:
- Inflation/deflation trend
- Remaining budget distribution across owners
- Positional demand curve
- Availability vs scarcity signal
- Replacement-level value by position

Wireframe:

```text
+------------------------------------------------------+
| Draft Dynamics                                       |
| Inflation Index: 1.12x (Inflating)                   |
| Budget Dist: Owner A $130 ######                     |
|              Owner B $98  ####                       |
| Demand/Scarcity:                                     |
| RB 12 need / 9 avail  [##########]                   |
| WR 9 need / 15 avail  [#####-----]                   |
| Replacement Level: RB $12.5, WR $9.2                 |
+------------------------------------------------------+
```

## Dynamic Update Behavior

Refresh insights when any of the following changes:
- selected player candidate
- bid amount
- draft history (new picks)
- owner context / budgets

Implementation details:
- Calls `POST /draft/model/predict`
- Uses debounced refresh (`~350ms`) to avoid UI thrash
- Includes `draft_state` for budget-aware capping

## Fallback and Explainability

When confidence is low (high-risk recommendation):
- Show explicit low-confidence fallback callout
- Encourage wider bid tolerance / alternate target check

Advanced metrics include plain-language help via `title` tooltips.

## Responsive behavior

- Desktop: 3-column analyzer layout (`Player`, `Owner`, `Dynamics`)
- Narrow screens: stacks into one column in same order
- Content remains textual and contrast-safe without color-only meaning

## Accessibility

- Metrics include text labels and thresholds, not color alone
- Progress bars paired with numeric text
- Tooltip copy describes each advanced metric in plain language

## Interpretation Guidance

Users should treat the analyzer as a co-pilot:
- `RecommendedBid` + `ConfidenceBand` => bid envelope
- `BargainFlag` + `BiddingPressure` => timing and pass/push choice
- `StrategyAlignment` + alerts => plan compliance
- `Dynamics` => when to pivot positions
