import pytest

from utils import github_issues


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http error: {self.status_code}")


REPORT_PAYLOAD = {
    "title": "Bug title",
    "description": "Something failed",
    "issue_type": "bug",
    "page_name": "Home",
    "page_url": "/",
    "email": "test@example.com",
    "created_at": "2026-03-08T00:00:00",
}


def test_create_bug_issue_uses_pat_as_primary(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "pat-token")
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY_PATH", raising=False)

    captured = {"auth": None}

    def fake_post(url, json=None, headers=None, timeout=None):
        assert "/repos/" in url
        captured["auth"] = headers.get("Authorization")
        return FakeResponse(
            status_code=201,
            payload={"html_url": "https://github.com/NPGrant81/fantasy-football-pi/issues/999"},
        )

    monkeypatch.setattr(github_issues.requests, "post", fake_post)

    issue = github_issues.create_bug_issue(REPORT_PAYLOAD)

    assert issue.get("html_url", "").endswith("/issues/999")
    assert captured["auth"] == "Bearer pat-token"


def test_create_bug_issue_falls_back_to_app_when_pat_fails(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "pat-token")
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "777")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----")

    call_log = []

    def fake_post(url, json=None, headers=None, timeout=None):
        call_log.append((url, headers.get("Authorization")))

        if "/repos/" in url and headers.get("Authorization") == "Bearer pat-token":
            return FakeResponse(status_code=401, payload={"message": "Bad credentials"})

        if "/app/installations/" in url:
            return FakeResponse(status_code=201, payload={"token": "app-install-token"})

        if "/repos/" in url and headers.get("Authorization") == "Bearer app-install-token":
            return FakeResponse(
                status_code=201,
                payload={"html_url": "https://github.com/NPGrant81/fantasy-football-pi/issues/1000"},
            )

        raise AssertionError(f"Unexpected request call: {url} {headers}")

    monkeypatch.setattr(github_issues.requests, "post", fake_post)
    monkeypatch.setattr(github_issues, "_get_app_jwt", lambda app_id, private_key: "app-jwt")

    issue = github_issues.create_bug_issue(REPORT_PAYLOAD)

    assert issue.get("html_url", "").endswith("/issues/1000")
    assert any("Bearer pat-token" == auth for _, auth in call_log)
    assert any("Bearer app-jwt" == auth for _, auth in call_log)
    assert any("Bearer app-install-token" == auth for _, auth in call_log)


def test_create_bug_issue_raises_when_no_auth_configured(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY_PATH", raising=False)

    with pytest.raises(RuntimeError) as exc:
        github_issues.create_bug_issue(REPORT_PAYLOAD)

    assert "not configured" in str(exc.value).lower()
