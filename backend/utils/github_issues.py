import logging
import os
import time
import requests
from jose import jwt

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_REPO = "NPGrant81/fantasy-football-pi"


def _get_private_key():
    key_path = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH")
    if key_path and os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as handle:
            return handle.read()

    raw_key = os.getenv("GITHUB_APP_PRIVATE_KEY")
    if raw_key:
        return raw_key.replace("\\n", "\n")

    return None


def _get_app_jwt(app_id, private_key):
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _get_installation_token(app_id, installation_id, private_key):
    app_jwt = _get_app_jwt(app_id, private_key)
    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("token")


def _create_issue(repo, token, title, body, labels):
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    response = requests.post(
        url,
        json={
            "title": title,
            "body": body,
            "labels": labels,
        },
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _resolve_token(app_id, installation_id, private_key):
    """Return a GitHub API token using PAT or GitHub App credentials.

    Priority:
    1. ``GITHUB_TOKEN`` environment variable (Personal Access Token)
    2. GitHub App installation token (requires App ID, installation ID, and
       private key)

    Raises ``RuntimeError`` when neither set of credentials is available.
    """
    pat = os.getenv("GITHUB_TOKEN")
    if pat:
        logger.debug("Using GITHUB_TOKEN (PAT) for GitHub API authentication")
        return pat

    if app_id and installation_id and private_key:
        logger.debug("Using GitHub App installation token for authentication")
        return _get_installation_token(app_id, installation_id, private_key)

    raise RuntimeError(
        "GitHub credentials are not configured. "
        "Set GITHUB_TOKEN (Personal Access Token) or configure GitHub App "
        "credentials (GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID, "
        "GITHUB_APP_PRIVATE_KEY / GITHUB_APP_PRIVATE_KEY_PATH)."
    )


def create_bug_issue(report, labels=None):
    app_id = os.getenv("GITHUB_APP_ID")
    installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID")
    repo = os.getenv("GITHUB_ISSUE_REPO", DEFAULT_REPO)
    private_key = _get_private_key()

    title = report["title"]
    body = "\n".join(
        [
            f"**Description**\n{report['description']}",
            "",
            f"**Issue Type:** {report.get('issue_type') or 'Not specified'}",
            f"**Page Name:** {report.get('page_name') or 'Not provided'}",
            f"**Page URL:** {report.get('page_url') or 'Not provided'}",
            f"**Reporter Email:** {report.get('email') or 'Not provided'}",
            f"**Reported At:** {report.get('created_at') or 'Just now'}",
        ]
    )

    label_list = labels or ["bug", "from-ui"]
    issue_type = (report.get("issue_type") or "").strip().lower()
    if issue_type:
        label_list.append(f"issue-type:{issue_type}")

    token = _resolve_token(app_id, installation_id, private_key)
    return _create_issue(repo, token, title, body, label_list)
