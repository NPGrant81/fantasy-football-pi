# backend/reset_db.py
from database import engine, Base
from models import User, League, LeagueSettings, ScoringRule, DraftPick, Player, Team

print("🔥 DESTROYING ALL DATA...")

# This drops all tables defined in your models
Base.metadata.drop_all(bind=engine)

print("✅ Database wiped clean.")
print("🚀 Re-creating tables...")

# This creates them fresh with the new 'is_superuser' column
Base.metadata.create_all(bind=engine)

print("✨ Tables created successfully! Now run 'python init_db.py'")