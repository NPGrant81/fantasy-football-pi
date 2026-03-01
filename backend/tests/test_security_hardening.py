from backend.routers import auth as auth_router


def test_root_includes_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("permissions-policy") is not None
    assert response.headers.get("cross-origin-opener-policy") == "same-origin"
    assert response.headers.get("content-security-policy") is not None


def test_login_rate_limiter_records_and_clears_attempts():
    key = "127.0.0.1:demo-user"
    auth_router.failed_login_attempts.clear()

    for _ in range(auth_router.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        auth_router._record_failed_attempt(key)

    assert auth_router._is_rate_limited(key)

    auth_router._clear_failed_attempts(key)

    assert not auth_router._is_rate_limited(key)
