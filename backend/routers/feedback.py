from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.security import get_current_user
from database import get_db
import models
from utils.email_sender import send_bug_report_email

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class BugReportCreate(BaseModel):
    title: str
    description: str
    page_url: Optional[str] = None
    severity: Optional[str] = None
    contact_email: Optional[str] = None


@router.post("/bug")
def create_bug_report(
    payload: BugReportCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not payload.title.strip() or not payload.description.strip():
        raise HTTPException(status_code=400, detail="Title and description are required")

    report = models.BugReport(
        user_id=current_user.id,
        email=payload.contact_email or current_user.email,
        title=payload.title.strip(),
        description=payload.description.strip(),
        page_url=payload.page_url,
        severity=payload.severity,
        status="OPEN",
        created_at=datetime.utcnow().isoformat()
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    send_bug_report_email(
        {
            "title": report.title,
            "description": report.description,
            "severity": report.severity,
            "page_url": report.page_url,
            "email": report.email,
            "created_at": report.created_at,
        }
    )

    return {"message": "Bug report submitted", "report_id": report.id}
