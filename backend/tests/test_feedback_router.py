from uuid import uuid4

from backend.database import SessionLocal
import backend.models as models
from backend.core import security
import backend.routers.feedback as feedback_router


def _seed_user():
    suffix = uuid4().hex[:8]
    session = SessionLocal()
    league_id = None
    user = None
    try:
        league = models.League(name=f"Feedback League {suffix}")
        session.add(league)
        session.commit()
        session.refresh(league)
        league_id = league.id

        user = models.User(
            username=f"feedback-user-{suffix}",
            email=f"feedback-{suffix}@example.com",
            hashed_password="h",
            league_id=league_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return {
            "league_id": league_id,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
        }
    finally:
        session.close()


def _cleanup_seeded_data(league_id):
    cleanup = SessionLocal()
    try:
        cleanup.query(models.BugReport).filter(
            models.BugReport.user_id.in_(
                cleanup.query(models.User.id).filter(models.User.league_id == league_id)
            )
        ).delete(synchronize_session=False)
        cleanup.query(models.User).filter(
            models.User.league_id == league_id
        ).delete(synchronize_session=False)
        cleanup.query(models.League).filter(
            models.League.id == league_id
        ).delete(synchronize_session=False)
        cleanup.commit()
    finally:
        cleanup.close()


def test_feedback_bug_report_returns_issue_url_when_github_succeeds(client, monkeypatch):
    seeded = _seed_user()

    def fake_create_bug_issue(_report):
        return {"html_url": "https://github.com/NPGrant81/fantasy-football-pi/issues/2001"}

    monkeypatch.setattr(feedback_router, "create_bug_issue", fake_create_bug_issue)

    try:
        token = security.create_access_token({"sub": seeded["username"]})
        client.cookies.set("ffpi_access_token", token)
        client.cookies.set("ffpi_csrf_token", "test-csrf-token")

        payload = {
            "title": "Bug test: successful issue",
            "description": "Repro steps here",
            "page_name": "Home",
            "issue_type": "bug",
            "page_url": "/",
            "contact_email": seeded["email"],
        }
        response = client.post(
            "/feedback/bug",
            json=payload,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("message") == "Bug report submitted"
        assert body.get("issue_url", "").endswith("/issues/2001")
        assert body.get("issue_warning") is None

        verify = SessionLocal()
        try:
            report = verify.query(models.BugReport).filter(
                models.BugReport.id == body.get("report_id")
            ).first()
            assert report is not None
            assert report.github_issue_url.endswith("/issues/2001")
        finally:
            verify.close()
    finally:
        client.cookies.clear()
        _cleanup_seeded_data(seeded["league_id"])


def test_feedback_bug_report_returns_warning_when_github_fails(client, monkeypatch):
    seeded = _seed_user()

    def fake_create_bug_issue(_report):
        raise RuntimeError("synthetic github failure")

    monkeypatch.setattr(feedback_router, "create_bug_issue", fake_create_bug_issue)

    try:
        token = security.create_access_token({"sub": seeded["username"]})
        client.cookies.set("ffpi_access_token", token)
        client.cookies.set("ffpi_csrf_token", "test-csrf-token")

        payload = {
            "title": "Bug test: warning path",
            "description": "Repro steps here",
            "page_name": "Home",
            "issue_type": "bug",
            "page_url": "/",
            "contact_email": seeded["email"],
        }
        response = client.post(
            "/feedback/bug",
            json=payload,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("message") == "Bug report submitted"
        assert body.get("issue_url") is None
        assert "GitHub issue not created" in str(body.get("issue_warning"))

        verify = SessionLocal()
        try:
            report = verify.query(models.BugReport).filter(
                models.BugReport.id == body.get("report_id")
            ).first()
            assert report is not None
            assert report.github_issue_url is None
            assert report.status == "OPEN"
        finally:
            verify.close()
    finally:
        client.cookies.clear()
        _cleanup_seeded_data(seeded["league_id"])
