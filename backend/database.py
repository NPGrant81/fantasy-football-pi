from sqlalchemy import create_engine
# SQLAlchemy 2.0 deprecates the old location of declarative_base
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Use an env-driven URL for runtime; fallback is a credential-free local DSN.
# In production/staging, DATABASE_URL should always be explicitly provided.
DEFAULT_DB_URL = "postgresql://localhost/fantasy_football"

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