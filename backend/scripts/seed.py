from sqlalchemy import text
from backend.core import security

# reuse models via import to avoid circularity
from .. import models


from sqlalchemy.orm import Session as SQLAlchemySession


def run_seeder(SessionLocal, get_password_hash):
    """Run the auto-seeding logic previously embedded in main.py.

    The caller may pass either the session factory (a sessionmaker) *or*
    an already-constructed :class:`sqlalchemy.orm.Session` instance. This
    tolerance makes the helper safer when the import context is weird (CI
    had once passed a concrete ``Session`` object by accident).
    """
    owns_session = False
    if isinstance(SessionLocal, SQLAlchemySession):
        db = SessionLocal
    else:
        # assume it's a factory
        db = SessionLocal()
        owns_session = True
    try:
        # make sure the future_draft_budget column exists before we query it
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS future_draft_budget INTEGER DEFAULT 0"))
            db.commit()
        except Exception:
            db.rollback()

        # Check for Admin User
        nick = db.query(models.User).filter(models.User.username == "Admin").first()
        if not nick:
            print("Auto-Seeding: Creating Admin...")
            nick = models.User(
                username="Admin",
                email="nick@example.com",
                hashed_password=get_password_hash("password"),
                is_commissioner=True,
                is_superuser=True,
                team_name="War Room Alpha"
            )
            db.add(nick)
            db.commit()
            db.refresh(nick)
        elif not security.verify_password("password", nick.hashed_password):
            # Self-heal known placeholder/broken hashes so local login remains usable
            # after test runs or partial restores.
            print("Auto-Seeding: Repairing Admin password hash...")
            nick.hashed_password = get_password_hash("password")
            db.commit()

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
        if owns_session:
            db.close()
