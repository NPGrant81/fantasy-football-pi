import os
import time
import requests
from jose import jwt

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


def create_bug_issue(report, labels=None):
    app_id = os.getenv("GITHUB_APP_ID")
    installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID")
    repo = os.getenv("GITHUB_ISSUE_REPO", DEFAULT_REPO)
    private_key = _get_private_key()

    if not app_id or not installation_id or not private_key:
        raise RuntimeError("GitHub App credentials are not configured")

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

    token = _get_installation_token(app_id, installation_id, private_key)
    return _create_issue(repo, token, title, body, label_list)
