import traceback

from backend.database import SessionLocal
from backend.routers.league import get_league_settings


def main() -> None:
    with SessionLocal() as db:
        try:
            settings = get_league_settings(1, db)
            print("Loaded settings:", settings)
        except Exception:
            print("Exception while fetching settings:")
            traceback.print_exc()


if __name__ == "__main__":
    main()
