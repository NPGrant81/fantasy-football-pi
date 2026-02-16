from sqlalchemy.orm import Session
from sqlalchemy import func, text  # <--- Added 'text' here
from database import SessionLocal
from models import User, DraftPick, Player

db = SessionLocal()

print(f"{'OWNER':<20} | {'TOTAL SPENT':<15} | {'BIGGEST SPLURGE'}")
print("-" * 60)

# Query: Join Users to Draft Picks to Players
results = db.query(
    User.username, 
    func.sum(DraftPick.amount).label('total_spent'),
    func.max(DraftPick.amount).label('max_bid')
).join(DraftPick).group_by(User.id).order_by(text("total_spent DESC")).all()

for row in results:
    # Find which player was the max bid (Biggest Splurge)
    # We query the DB again to find the specific player associated with that max bid amount
    user_id = db.query(User).filter(User.username == row.username).first().id
    
    top_pick = db.query(Player).join(DraftPick).filter(
        DraftPick.owner_id == user_id,
        DraftPick.amount == row.max_bid
    ).first()
    
    player_name = top_pick.name if top_pick else "N/A"
    print(f"{row.username:<20} | ${row.total_spent:,.2f}       | ${row.max_bid} ({player_name})")