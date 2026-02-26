from sqlalchemy import text

# reuse models via import to avoid circularity
from .. import models


def run_seeder(SessionLocal, get_password_hash):
    """Run the auto-seeding logic previously embedded in main.py.

    This function accepts the SessionLocal factory and password hashing
    helper from the caller so the module can remain "backend-agnostic" and
    be invoked from tests or manual scripts as needed.
    """
    db = SessionLocal()
    try:
        # make sure the future_draft_budget column exists before we query it
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS future_draft_budget INTEGER DEFAULT 0"))
            db.commit()
        except Exception:
            db.rollback()

        # Check for Admin User
        nick = db.query(models.User).filter(models.User.username == "Nick Grant").first()
        if not nick:
            print("Auto-Seeding: Creating Nick Grant...")
            nick = models.User(
                username="Nick Grant",
                email="nick@example.com",
                hashed_password=get_password_hash("password"),
                is_commissioner=True,
                is_superuser=True,
                team_name="War Room Alpha"
            )
            db.add(nick)
            db.commit()
            db.refresh(nick)

        # Check for Default League
        test_league = db.query(models.League).filter(models.League.name == "The Big Show").first()
        if not test_league:
            print("Auto-Seeding: Creating 'The Big Show' League...")
            test_league = models.League(name="The Big Show")
            db.add(test_league)
            db.commit()
            db.refresh(test_league)

            # Link Nick to the new league
            nick.league_id = test_league.id
            db.commit()

        print("Auto-Seeding Complete.")
    finally:
        db.close()
