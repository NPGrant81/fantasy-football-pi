# backend/scripts/reset_db.py
# DANGER: This script drops ALL tables and recreates them, destroying all data.
# It must be run explicitly with RESET_DB_CONFIRMED=true to prevent accidents.
import os
import sys

if os.environ.get("RESET_DB_CONFIRMED", "").lower() not in ("true", "1", "yes"):
    print("ERROR: Refusing to wipe database. Set RESET_DB_CONFIRMED=true to confirm.")
    print("  e.g.: RESET_DB_CONFIRMED=true python -m backend.scripts.reset_db")
    sys.exit(1)

from database import engine, Base
# Removed 'Team' from the import list since it's not in models.py
from models import User, League, LeagueSettings, ScoringRule, DraftPick, Player, Matchup

print("🔥 DESTROYING ALL DATA...")

# Base.metadata knows about all classes that inherit from Base
Base.metadata.drop_all(bind=engine)

print("✅ Database wiped clean.")
print("🚀 Re-creating tables...")

Base.metadata.create_all(bind=engine)

print("✨ Tables created successfully! Columns like 'draft_status' and 'is_superuser' are now live.")