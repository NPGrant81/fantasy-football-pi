# backend/scripts/reset_db.py
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