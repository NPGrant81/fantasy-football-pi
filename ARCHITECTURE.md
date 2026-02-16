War Room Alpha: Technical Architecture
This document outlines the high-level organization and logical patterns of the War Room Alpha backend.
1. Directory Structure
The project follows a Service-Oriented Architecture to separate web interfaces from core business logic.


backend/
├── core/              # 1.1 Security, Auth context, and Constants
├── data/              # 1.2 Raw CSV files (Players, Teams, Rules)
├── routers/           # 1.3 FastAPI route definitions (The Front Door)
├── services/          # 1.4 Business logic and DB operations (The Engine)
├── scripts/           # 1.5 CLI tools (Reset, Seed, Sync)
├── models.py          # 1.6 SQLAlchemy database models
├── database.py        # 1.7 Database engine and session setup
└── main.py            # 1.8 Application entry point


2. Logic Numbering Standard
To maintain a consistent flow across routers and services, all functions follow a tiered numbering system within code comments:
1.x: Validation & Data Retrieval
• 1.1 Security Checks: Verify JWT tokens or user roles (e.g., Commissioner/Superuser).
• 1.2 Data Sourcing: Fetch required records from the database or external APIs.
• 1.3 Input Validation: Ensure the incoming request meets business rules (e.g., checking roster limits).
2.x: Execution & Response
• 2.1 Core Action: Perform the primary task (e.g., adding a player, calculating a score).
• 2.2 Persistence: Commit changes to the PostgreSQL database.
• 2.3 Response: Return the final status and payload to the client.
3. Core Logic Layers
Scoring Service
The scoring_service.py is the primary engine for calculating performance. It pulls dynamic rules from the ScoringRule table, allowing different leagues to maintain unique scoring settings without code changes.
Security Bouncers
Access control is managed via FastAPI Dependencies in core/security.py. These act as "bouncers" at the router level, preventing non-commissioners from accessing administrative endpoints.
Seeding & Maintenance
One-time setup tasks and destructive actions (like resetting the draft) are isolated in the scripts/ folder. This ensures that "nuclear" logic is never accidentally executed by the web server.
Why this works:
• Separation of Concerns: You can update the "Waiver Claim" logic in the service layer without touching the API endpoint in the router.
• Scalability: New features (like Trades or Playoff Brackets) have a clear, predetermined home in the directory tree.
• AI Coordination: Maintaining this file helps AI tools understand your specific architectural invariants, leading to better code suggestions.

Since we are moving to a professional, self-hosted setup on your Raspberry Pi, the architecture needs to transition from "script-based" to "service-based." This schema reflects a modern FastAPI + PostgreSQL stack designed for performance and reliability.
4.0 Backend Infrastructure Schema
The backend is built on a Layered Architecture to ensure that data logic, business rules, and API endpoints stay separated. This prevents "spaghetti code" and makes debugging from your phone much easier.
4.1 Layered Logic Stack
1. Routers (/api/v1/routers): The "Front Desk." They receive requests, validate the user's JWT token via the "Bouncer" (security.py), and hand the work off to the Services.
2. Services (/api/v1/services): The "Brain." This is where the heavy lifting happens—calculating complex scoring, processing auction bids, and managing draft logic.
3. Models (/models): The "Blueprint." Defines exactly how a User, Player, or League looks in the database.
4. Schemas (/schemas): The "Contract." Uses Pydantic to define what the JSON data looks like coming in and going out of the API.
4.2 Data & Persistence Layer
• Primary DB: PostgreSQL. Handles relational data like League standings and Roster history.
• Real-time Layer: Redis (Optional/Future). Recommended for the "War Room" auction timer and live chat to reduce the load on the Pi’s SD card.
• Migration Tool: Alembic. Manages database versioning so you can update your schema without losing your draft data.
4.3 Deployment & Networking


4.4 The "Bouncer" (Security) Logic
The infrastructure relies on JWT (JSON Web Tokens) for stateless authentication:
1. User provides credentials to /auth/token.
2. Backend verifies and returns a signed token.
3. Frontend stores this in localStorage and includes it in the Authorization: Bearer <token> header for all future calls via apiClient.
4. Infrastructure verifies the signature at the Router level before allowing access to Service logic.
4.5 Production Environment Variables
To keep your "Locker Room" secure, sensitive data is never hardcoded. We use a .env file on the Pi:
• DATABASE_URL: Connection string for Postgres.
• SECRET_KEY: High-entropy string for signing JWTs.
• ENVIRONMENT: Set to production or development.

