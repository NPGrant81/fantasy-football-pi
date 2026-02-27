from sqlalchemy import create_engine
# SQLAlchemy 2.0 deprecates the old location of declarative_base
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# FIX: Update this string to match your local setup!
# Usually: postgresql://postgres:<password>@localhost/fantasy_pi
# the Pi’s local installation uses password `football-pi` and a database
# called `fantasy_football` (the connection string shown matches what you would
# use in Azure Data Studio).
DEFAULT_DB_URL = "postgresql://postgres:football-pi@localhost/fantasy_football"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session in API calls
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()