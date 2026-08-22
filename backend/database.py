from sqlalchemy import create_engine, text
# SQLAlchemy 2.0 deprecates the old location of declarative_base
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.core.config import get_settings
from backend.db_config import load_backend_env_file, resolve_database_url

load_backend_env_file()
runtime_settings = get_settings()

SQLALCHEMY_DATABASE_URL = runtime_settings.database_url or resolve_database_url(
    require_explicit=False,
    context="backend runtime",
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def probe_database(database_engine=engine) -> None:
    with database_engine.connect() as connection:
        connection.execute(text("SELECT 1"))


# Dependency to get DB session in API calls
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
