from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.security import get_current_user
from database import get_db
import models
from utils.github_issues import create_bug_issue

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class BugReportCreate(BaseModel):
    title: str
    description: str
    page_name: Optional[str] = None
    issue_type: Optional[str] = None
    page_url: Optional[str] = None
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
        page_name=payload.page_name,
        issue_type=payload.issue_type,
        page_url=payload.page_url,
        status="OPEN",
        created_at=datetime.utcnow().isoformat()
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    issue_payload = {
        "title": report.title,
        "description": report.description,
        "issue_type": report.issue_type,
        "page_name": report.page_name,
        "page_url": report.page_url,
        "email": report.email,
        "created_at": report.created_at,
    }

    issue_warning = None
    try:
        issue = create_bug_issue(issue_payload)
        report.github_issue_url = issue.get("html_url")
        db.commit()
    except Exception as exc:
        issue_warning = f"GitHub issue not created: {exc}"

    return {
        "message": "Bug report submitted",
        "report_id": report.id,
        "issue_url": report.github_issue_url,
        "issue_warning": issue_warning,
    }
