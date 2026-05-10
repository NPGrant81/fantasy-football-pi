from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.scripts.daily_sync import sync_nfl_reality

from ..core.security import check_is_commissioner
from ..database import get_db
from ..services import admin_audit_service

router = APIRouter(prefix="/admin/nfl", tags=["Admin NFL"])


@router.post("/sync")
async def trigger_nfl_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(check_is_commissioner),
):
    """
    Triggers the 'Daily Truth' sync script.
    Runs in the background so it doesn't freeze your UI.
    """
    background_tasks.add_task(sync_nfl_reality)
    admin_audit_service.record_privileged_action(
        db,
        current_user,
        "trigger_nfl_sync",
        "commissioner",
        metadata_json={"route": "admin_nfl.sync"},
    )
    return {"message": "NFL Reality Sync started in the background!"}


class ScheduleImportPayload(BaseModel):
    year: int
    week: int | None = None


@router.post("/schedule/import")
async def trigger_schedule_import(
    payload: ScheduleImportPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(check_is_commissioner),
):
    """
    Runs the NFL schedule importer for the given year (and optional week).
    This will hit ESPN and upsert rows into `nfl_games`.  The operation runs in
    a background task because the third-party API can be slow.
    """
    from backend.scripts.import_nfl_schedule import upsert_games

    year = payload.year
    week = payload.week
    background_tasks.add_task(upsert_games, year, week)
    detail = f"Schedule import started for {year}"
    if week is not None:
        detail += f" week {week}"
    admin_audit_service.record_privileged_action(
        db,
        current_user,
        "trigger_schedule_import",
        "commissioner",
        metadata_json={"route": "admin_nfl.schedule_import", "year": year, "week": week},
    )
    return {"detail": detail}