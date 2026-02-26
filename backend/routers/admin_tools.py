# backend/routers/admin_tools.py
from fastapi import APIRouter, BackgroundTasks, Depends
# when running under the `backend` package we need the full path
# because the top-level `scripts` package is not on sys.path by default.
from backend.scripts.daily_sync import sync_nfl_reality
from ..core.security import check_is_commissioner

router = APIRouter(prefix="/admin/tools", tags=["Admin Tools"])

@router.post("/sync-nfl")
async def trigger_nfl_sync(background_tasks: BackgroundTasks, current_user=Depends(check_is_commissioner)):
    """
    Triggers the 'Daily Truth' sync script. 
    Runs in the background so it doesn't freeze your UI.
    """
    background_tasks.add_task(sync_nfl_reality)
    return {"message": "NFL Reality Sync started in the background!"}


from pydantic import BaseModel


class ScheduleImportPayload(BaseModel):
    year: int
    week: int | None = None


@router.post("/import-nfl-schedule")
async def trigger_schedule_import(
    payload: ScheduleImportPayload,
    background_tasks: BackgroundTasks,
    current_user=Depends(check_is_commissioner),
):
    """
    Runs the NFL schedule importer for the given year (and optional week).
    This will hit ESPN and upsert rows into `nfl_games`.  The operation runs in
    a background task because the third-party API can be slow.

    Request body example:
    {
        "year": 2026,
        "week": 1   # optional
    }
    """
    # import lazily using the backend namespace for the same reason as
    # above (package context may differ between CLI scripts and uvicorn).
    from backend.scripts.import_nfl_schedule import upsert_games

    year = payload.year
    week = payload.week
    background_tasks.add_task(upsert_games, year, week)
    detail = f"Schedule import started for {year}"
    if week is not None:
        detail += f" week {week}"
    return {"detail": detail}
