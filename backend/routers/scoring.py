from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Import your new structure
from database import get_db
import models
import schemas
from auth import get_current_league_commissioner

router = APIRouter(
    prefix="/scoring",
    tags=["scoring"]
)

# 1. GET ALL RULES (Read-Only for Users)
@router.get("/", response_model=List[schemas.ScoringRule])
def read_scoring_rules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rules = db.query(models.ScoringRule).offset(skip).limit(limit).all()
    return rules

# 2. CREATE A NEW RULE (Commissioner Only)
@router.post("/", response_model=schemas.ScoringRule)
def create_scoring_rule(
    rule: schemas.ScoringRuleCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_league_commissioner) # <--- SECURITY CHECK
):
    db_rule = models.ScoringRule(**rule.dict(), league_id=current_user.league_id)
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

# 3. DELETE A RULE (Commissioner Only)
@router.delete("/{rule_id}")
def delete_scoring_rule(
    rule_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_league_commissioner)
):
    rule = db.query(models.ScoringRule).filter(models.ScoringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Ensure Commish only deletes rules for THEIR league
    if rule.league_id != current_user.league_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this rule")

    db.delete(rule)
    db.commit()
    return {"ok": True}
