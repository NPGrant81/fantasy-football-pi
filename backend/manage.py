"""Utility script for ad-hoc backend tasks.

Run `python -m backend.manage seed` to populate the database with the
default admin user + sample league.  This replaces the previous startup
handler, eliminating the need for every test to trigger the seeder.
"""

import click

from .database import SessionLocal, engine, Base
from .scripts.seed import run_seeder
from .core.security import get_password_hash


@click.group()
def cli():
    pass


@cli.command()
def seed():
    """Execute the auto-seeder using the session factory.

    Before seeding we must ensure the schema exists – the original
    startup handler created the tables for us, but running the seeder as a
    standalone command means the database can be completely empty.
    """
    # create tables if missing (works with any SQLAlchemy dialect)
    print("Creating database tables…")
    Base.metadata.create_all(bind=engine)

    print("Running seeder…")
    run_seeder(SessionLocal, get_password_hash)


if __name__ == "__main__":
    cli()
