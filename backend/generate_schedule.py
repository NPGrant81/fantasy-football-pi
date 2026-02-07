from sqlalchemy.orm import Session
# FIX: Removed "backend." prefix since we are now INSIDE the folder
from database import SessionLocal, engine
import models
import random

# 1. Initialize DB
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

def generate_schedule():
    print("📅 Generating 14-Week Fantasy Schedule...")

    # 2. Get All Owners
    owners = db.query(models.User).all()
    if len(owners) < 2:
        print("❌ Not enough teams to create a schedule!")
        return

    # Shuffle for randomness
    random.shuffle(owners)
    
    # If odd number of teams, add a "Bye" (None)
    if len(owners) % 2 != 0:
        owners.append(None)
    
    num_teams = len(owners)
    weeks = 14 # Standard Fantasy Regular Season
    
    # Clear old schedule
    # Note: This wipes the schedule table clean!
    try:
        db.query(models.Matchup).delete()
        db.commit()
    except Exception as e:
        print(f"⚠️ Warning cleaning table: {e}")
        db.rollback()

    # FIX: Exclude "Free Agent" and "Obsolete"
    owners = db.query(models.User).filter(
        models.User.username.not_in(["Free Agent", "Obsolete", "free agent", "obsolete"])
    ).all()

    # 3. Round Robin Algorithm (Circle Method)
    # Fix the first team, rotate the rest
    if owners[0]:
        fixed_team = owners[0]
        rotating_teams = owners[1:]
    else:
        # Handle case where first shuffle is None (rare/edge case)
        fixed_team = owners[1]
        rotating_teams = [owners[0]] + owners[2:]

    current_teams = [fixed_team] + rotating_teams

    for week in range(1, weeks + 1):
        print(f"   - Scheduling Week {week}...")
        
        # Split into two halves
        half = len(current_teams) // 2
        home_teams = current_teams[:half]
        away_teams = current_teams[half:][::-1] # Reverse the second half
        
        for home, away in zip(home_teams, away_teams):
            # Skip games if there's a "Bye" (Ghost team)
            if home is None or away is None:
                continue

            # Randomize Home/Away field advantage
            if random.choice([True, False]):
                h, a = home, away
            else:
                h, a = away, home
                
# ... inside the loop where we create Matchup ...
            
            # Generate Mock Scores for Demo
            matchup = models.Matchup(
                week=week,
                home_team_id=h.id,
                away_team_id=a.id,
                home_score=0.0,
                away_score=0.0,
                # NEW: Mock Projections (100-140 points)
                home_projected=round(random.uniform(95, 145), 2),
                away_projected=round(random.uniform(95, 145), 2),
                is_completed=False
            )
            db.add(matchup)

        # Rotate the list for next week
        # Keep fixed_team at [0], rotate the rest
        # List slicing: [last item] + [rest of items]
        rotating_teams = [rotating_teams[-1]] + rotating_teams[:-1]
        current_teams = [fixed_team] + rotating_teams

    db.commit()
    print("✅ Schedule Generated Successfully!")

if __name__ == "__main__":
    generate_schedule()