# backend/init_db.py
from database import SessionLocal, engine, Base
from models import User, League, LeagueSettings, ScoringRule
from auth import get_password_hash

# 1. Create the Database Tables (This happens automatically mostly, but good to be safe)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

print("🚀 Starting Database Initialization...")

# 2. Create the "Post Pacific League"
existing_league = db.query(League).filter(League.name == "Post Pacific League").first()
if not existing_league:
    new_league = League(name="Post Pacific League")
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    print(f"✅ League Created: {new_league.name} (ID: {new_league.id})")
    
    # Add Default Settings
    db.add(LeagueSettings(league_id=new_league.id))
    
    # Add Default Rules
    default_rules = [
        ScoringRule(league_id=new_league.id, category="Passing", description="Passing TD", points=4.0),
        ScoringRule(league_id=new_league.id, category="Rushing", description="Rushing TD", points=6.0),
        ScoringRule(league_id=new_league.id, category="Receiving", description="Reception (PPR)", points=1.0),
    ]
    db.add_all(default_rules)
    db.commit()
    league_id = new_league.id
else:
    print("⚠️  League already exists. Skipping creation.")
    league_id = existing_league.id

# 3. Create the SUPER USER (You!)
existing_user = db.query(User).filter(User.username == "Nick_Grant").first()
if not existing_user:
    pw = get_password_hash("password")
    
    # This is the "God Mode" user
    admin = User(
        username="Nick_Grant", 
        hashed_password=pw, 
        is_superuser=True,      # <--- Site Admin
        is_commissioner=True,   # <--- League Manager
        league_id=league_id     # <--- Assigned to the main league
    )
    
    db.add(admin)
    db.commit()
    print("👑 Super User 'Nick_Grant' created with password: 'password'")
else:
    print("⚠️  User 'Nick_Grant' already exists.")

print("\n✨ Initialization Complete! You can now log in.")