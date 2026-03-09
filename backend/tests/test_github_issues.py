"""Tests for backend/utils/github_issues.py"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.github_issues import _resolve_token, create_bug_issue

SAMPLE_REPORT = {
    "title": "Test bug",
    "description": "Something broke",
    "issue_type": "bug",
    "page_name": "My Team",
    "page_url": "/team",
    "email": "user@example.com",
    "created_at": "2024-01-01T00:00:00",
}


# ---------------------------------------------------------------------------
# _resolve_token
# ---------------------------------------------------------------------------


def test_resolve_token_uses_pat_when_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)

    token = _resolve_token(None, None, None)
    assert token == "ghp_testtoken"


def test_resolve_token_uses_pat_over_app_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_pat")
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "67890")

    with patch("utils.github_issues._get_installation_token") as mock_install:
        token = _resolve_token("12345", "67890", "fake-key")
        assert token == "ghp_pat"
        mock_install.assert_not_called()


def test_resolve_token_uses_app_when_no_pat(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with patch("utils.github_issues._get_installation_token", return_value="app_token") as mock_install:
        token = _resolve_token("12345", "67890", "fake-key")
        assert token == "app_token"
        mock_install.assert_called_once_with("12345", "67890", "fake-key")


def test_resolve_token_raises_when_no_credentials(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="GitHub credentials are not configured"):
        _resolve_token(None, None, None)


def test_resolve_token_raises_when_app_creds_incomplete(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    # Missing installation_id
    with pytest.raises(RuntimeError, match="GitHub credentials are not configured"):
        _resolve_token("12345", None, "fake-key")


# ---------------------------------------------------------------------------
# create_bug_issue
# ---------------------------------------------------------------------------


def test_create_bug_issue_with_pat(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    monkeypatch.setenv("GITHUB_ISSUE_REPO", "owner/repo")
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY_PATH", raising=False)

    fake_response = {"html_url": "https://github.com/owner/repo/issues/1", "number": 1}
    with patch("utils.github_issues._create_issue", return_value=fake_response) as mock_create:
        result = create_bug_issue(SAMPLE_REPORT)

    assert result["html_url"] == "https://github.com/owner/repo/issues/1"
    mock_create.assert_called_once()
    _args = mock_create.call_args
    assert _args[0][0] == "owner/repo"
    assert _args[0][1] == "ghp_testtoken"


def test_create_bug_issue_raises_when_no_credentials(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY_PATH", raising=False)

    with pytest.raises(RuntimeError, match="GitHub credentials are not configured"):
        create_bug_issue(SAMPLE_REPORT)


def test_create_bug_issue_body_contains_fields(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    monkeypatch.setenv("GITHUB_ISSUE_REPO", "owner/repo")

    captured = {}

    def fake_create_issue(repo, token, title, body, labels):
        captured["body"] = body
        captured["title"] = title
        captured["labels"] = labels
        return {"html_url": "https://github.com/owner/repo/issues/2"}

    with patch("utils.github_issues._create_issue", side_effect=fake_create_issue):
        create_bug_issue(SAMPLE_REPORT)

    assert "Something broke" in captured["body"]
    assert "My Team" in captured["body"]
    assert "/team" in captured["body"]
    assert "user@example.com" in captured["body"]
    assert captured["title"] == "Test bug"
    assert "bug" in captured["labels"]
    assert "from-ui" in captured["labels"]
    assert "issue-type:bug" in captured["labels"]
