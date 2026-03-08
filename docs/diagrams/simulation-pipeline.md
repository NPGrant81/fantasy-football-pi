# Simulation Pipeline (Draft Strategy Simulator)

This diagram outlines the Monte Carlo simulation pipeline used to model auction draft strategies, roster outcomes, and projected value distributions.

```mermaid
flowchart TD
    A[Input: League Settings + Player Projections] --> B[Initialize Simulation]
    B --> C[Run N Iterations]
    C --> D[Simulate Auction Dynamics]
    D --> E[Simulate Roster Outcomes]
    E --> F[Calculate Points + Value]
    F --> G[Aggregate Results]
    G --> H[Compute Percentiles + Spend Profile]
    H --> I[Generate Key Target Probabilities]
    I --> J[Return JSON Result to UI]
```
