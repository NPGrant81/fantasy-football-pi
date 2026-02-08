# fantasy-football-pi

 Fantasy Football Pi (The "War Room")A self-hosted, Python-based Fantasy Football platform designed to run on a Raspberry Pi (or local PC). It features a custom Auction Draft engine, weekly matchups with live NFL data, and a Commissioner "God Mode" dashboard.
 🚀 Features
 1. The Draft Engine
 Auction Style: Real-time bidding interface.
 Nominations: Owners take turns nominating players.
 Draft Board: A public-facing "Big Board" optimized for TV display.
 Live Budget Tracking: Automatically deducts winning bids from team budgets.
 2. Team Management
 Roster Management: Set Starters vs. Bench.
 Live NFL Data: Integrated with nfl_data_py to pull real-time 2025 rosters (excluding retired players like Sam Bradford).
 Validation: Prevents submitting invalid lineups (e.g., too many QBs).
 3. Weekly Matchups
 Schedule Generation: Automated round-robin schedule builder.
 Game Center: View live matchups with side-by-side roster comparisons.
 Scoring Engine: Calculates projected scores based on active starters.
 4. Commissioner "God Mode"
 League Settings: Edit Roster Size, Salary Cap, and Scoring Rules via UI.
 Complex Scoring: Supports tiered scoring (e.g., specific bonuses for 40+ yard TDs or 100-199 yard games).
 Recruitment Tool: Admin can force-move users into specific leagues.
 
 🛠️ Tech StackBackend: FastAPI (Python), SQLAlchemy, SQLite (Database).Frontend: React (Vite), Tailwind CSS.Data Source: nfl_data_py (Python wrapper for nflverse).
 
 ⚙️ Setup & Installation
 1. Backend Setup
 Navigate to the backend folder and activate the virtual environment:PowerShellcd backend
# Activate venv (Windows)
venv\Scripts\activate 
# Install dependencies
pip install -r requirements.txt
2. Frontend Setup
Navigate to the frontend folder:PowerShellcd frontend
npm install
npm run dev
🤖 Administration Scripts (The "Nuclear Option")These scripts located in backend/ are used to reset or manage the database.Script NameDescriptionpython init_league.pyWARNING: Wipes the entire database. Recreates tables, creates the "Post Pacific League," creates the Admin user (Nick Grant / password), and loads complex scoring rules.python import_nfl_data.pyFetches live 2025 player data from NFL servers and populates the players table.python seed_draft.pySimulates a full auction draft for 12 teams. Assigns Starters/Bench automatically. Useful for testing post-draft features.python generate_schedule.pyGenerates a 14-week round-robin schedule for all teams in the league.Standard Reset Protocol (If things break):python init_league.pypython import_nfl_data.pypython seed_draft.pypython generate_schedule.py
🔑 Login CredentialsCommissioner 
(Admin):Username: Nick Grant
Password: passwordRegular Owners:Username: Owner_1 ... Owner_11Password: password🐛 Troubleshooting"No Leagues Found" / Stuck LoadingCause: The browser has an old JWT token from a previous database version.Fix:Open Developer Tools (F12) -> Application -> Local Storage.Delete the token key.Refresh the page and log in again."Foreign Key Violation" when running scriptsCause: Trying to delete a table (like Users) that other tables (like Budgets) depend on.Fix: Run init_league.py first (it uses CASCADE to force-delete), then run the other scripts.Player Search returns old playersCause: The database has stale data.Fix: Run python import_nfl_data.py to fetch the fresh 2025 roster set.Matchups show empty scoresCause: The drafted players might be set to "BENCH".Fix: Go to "My Team" and submit a lineup, or re-run python seed_draft.py which automatically sets starters.📝 Todo List (Future Work)[ ] Waiver Wire: Allow picking up free agents.[ ] Live Scoring: Connect nfl_data_py to fetch actual weekly stats (currently using projections).[ ] Standings Page: Display Win/Loss records and Points For.Final Step for TodayStop all servers.Commit everything:PowerShellgit add .
git commit -m "docs: added comprehensive README and finalized Commissioner Tools"
git push