# backend/uat/seed_owners.py
from sqlalchemy.orm import Session
import models
from core.security import get_password_hash

def seed_owners(db: Session):
    print("👤 SEEDING OWNERS: Creating the 12-team league...")

    # 1.1 VALIDATION: Ensure 'The Big Show' league exists
    league = db.query(models.League).filter(models.League.name == "The Big Show").first()
    if not league:
        league = models.League(name="The Big Show")
        db.add(league)
        db.commit()
        db.refresh(league)

    # 1.2 DATA: Define the roster of 12 unique owners
    owner_list = [
        {"username": "Nick Grant", "email": "nick@example.com", "commish": True, "team": "War Room Alpha"},
        {"username": "Draft Dodger", "email": "dodger@example.com", "commish": False, "team": "Empty Bench Mob"},
        {"username": "Stats Geek", "email": "geek@example.com", "commish": False, "team": "Regression To The Mean"},
        {"username": "Trade Junkie", "email": "junkie@example.com", "commish": False, "team": "Always Countering"},
        {"username": "Waiver Wire King", "email": "king@example.com", "commish": False, "team": "Priority One"},
        {"username": "Gridiron Guru", "email": "guru@example.com", "commish": False, "team": "X and O Experts"},
        {"username": "Fantasy Phenom", "email": "phenom@example.com", "commish": False, "team": "Phenom Phantasy"},
        {"username": "Lucky Lefty", "email": "lefty@example.com", "commish": False, "team": "Standard Deviation"},
        {"username": "Redzone Rebel", "email": "rebel@example.com", "commish": False, "team": "Points Only"},
        {"username": "Sleeper Scout", "email": "scout@example.com", "commish": False, "team": "Depth Chart Divas"},
        {"username": "PPR Powerhouse", "email": "ppr@example.com", "commish": False, "team": "Reception Addiction"},
        {"username": "Bench Boss", "email": "boss@example.com", "commish": False, "team": "Decision Fatigue"},
    ]

    # 2.1 EXECUTION: Create users with shared password 'password'
    for data in owner_list:
        exists = db.query(models.User).filter(models.User.username == data["username"]).first()
        if not exists:
            user = models.User(
                username=data["username"],
                email=data["email"],
                hashed_password=get_password_hash("password"),
                is_commissioner=data["commish"],
                is_superuser=data["commish"],
                league_id=league.id,
                team_name=data["team"]
            )
            db.add(user)
    
    db.commit()
    print(f"✅ Owners seeded for '{league.name}'.")