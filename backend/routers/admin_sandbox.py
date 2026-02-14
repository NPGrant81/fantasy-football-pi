# backend/routers/admin_sandbox.py
from fastapi import APIRouter, Depends
import models

router = APIRouter(prefix="/admin/sandbox", tags=["Admin"])

@router.post("/clone/{league_id}")
def clone_league_for_testing(league_id: int):
    # Logic to copy league settings and rules to a new ID
    # This keeps your 'Post Pacific League' safe while you break things elsewhere
    return {"message": f"Sandbox League created from League {league_id}"}
