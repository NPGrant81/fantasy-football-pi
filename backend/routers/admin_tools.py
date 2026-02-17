# backend/routers/admin_tools.py
from fastapi import APIRouter, BackgroundTasks, Depends
from scripts.daily_sync import sync_nfl_reality
from core.security import check_is_commissioner

router = APIRouter(prefix="/admin/tools", tags=["Admin Tools"])

@router.post("/sync-nfl")
async def trigger_nfl_sync(background_tasks: BackgroundTasks, current_user=Depends(check_is_commissioner)):
    """
    Triggers the 'Daily Truth' sync script. 
    Runs in the background so it doesn't freeze your UI.
    """
    background_tasks.add_task(sync_nfl_reality)
    return {"message": "NFL Reality Sync started in the background!"}
