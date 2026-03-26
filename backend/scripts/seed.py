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

        # Check for dedicated Admin superuser (not a league owner)
        admin = db.query(models.User).filter(models.User.username == "Admin").first()
        if not admin:
            print("Auto-Seeding: Creating Admin...")
            admin = models.User(
                username="Admin",
                email="admin@postpacific.local",
                hashed_password=get_password_hash("password"),
                is_commissioner=True,
                is_superuser=True,
                league_id=None,
                team_name=None,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        elif not security.verify_password("password", admin.hashed_password):
            # Self-heal known placeholder/broken hashes so local login remains usable
            # after test runs or partial restores.
            print("Auto-Seeding: Repairing Admin password hash...")
            admin.hashed_password = get_password_hash("password")
            db.commit()

        # Ensure Admin remains detached from league ownership views.
        if admin.league_id is not None or admin.team_name is not None:
            admin.league_id = None
            admin.team_name = None
            db.commit()

        # Check for Default League
        test_league = db.query(models.League).filter(models.League.name == "The Big Show").first()
        if not test_league:
            print("Auto-Seeding: Creating 'The Big Show' League...")
            test_league = models.League(name="The Big Show")
            db.add(test_league)
            db.commit()
            db.refresh(test_league)

            # No automatic owner-linking in startup seeder.

        print("Auto-Seeding Complete.")
    finally:
        if owns_session:
            db.close()
