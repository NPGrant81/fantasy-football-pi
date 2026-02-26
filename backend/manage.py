"""Utility script for ad-hoc backend tasks.

Run `python -m backend.manage seed` to populate the database with the
default admin user + sample league.  This replaces the previous startup
handler, eliminating the need for every test to trigger the seeder.
"""

import click

from .database import SessionLocal
from .scripts.seed import run_seeder
from .core.security import get_password_hash


@click.group()
def cli():
    pass


@cli.command()
def seed():
    """Execute the auto-seeder using the session factory.

    ``run_seeder`` is already tolerant of receiving either a factory or an
    existing ``Session``.  Passing the factory keeps the responsibility of
    session creation/teardown inside ``run_seeder`` and avoids the TypeError
    we saw in CI.
    """
    run_seeder(SessionLocal, get_password_hash)


if __name__ == "__main__":
    cli()
