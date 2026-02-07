from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# FIX: Update this string to match your local setup!
# Usually: postgresql://postgres:password123@localhost/fantasy_pi
DEFAULT_DB_URL = "postgresql://postgres:password123@localhost/fantasy_pi"

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