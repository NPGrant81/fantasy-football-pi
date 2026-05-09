"""
Tests for the distributed rate limiter service.

Validates both in-memory and Redis-backed implementations.
"""

import pytest
import time
from backend.services import rate_limiter_service


@pytest.fixture
def limiter():
    """Provide a fresh rate limiter instance for each test."""
    # Force in-memory backend for testing
    rate_limiter_service._rate_limiter = rate_limiter_service.InMemoryRateLimiter()
    limiter = rate_limiter_service.get_rate_limiter()
    yield limiter
    # Cleanup
    rate_limiter_service._rate_limiter = None


class TestInMemoryRateLimiter:
    """Test in-memory rate limiter."""

    def test_allows_attempts_below_limit(self, limiter):
        """Should allow attempts below the limit."""
        key = "test:user:127.0.0.1"
        max_attempts = 3
        window_seconds = 10

        # Record 2 attempts (below limit of 3)
        limiter.record_attempt(key)
        limiter.record_attempt(key)

        # Should not be rate limited
        assert not limiter.is_rate_limited(key, max_attempts, window_seconds)
        assert limiter.get_remaining_attempts(key, max_attempts, window_seconds) == 1

    def test_blocks_at_limit(self, limiter):
        """Should block when max attempts is reached."""
        key = "test:user:127.0.0.1"
        max_attempts = 3
        window_seconds = 10

        # Record 3 attempts (at limit)
        for _ in range(max_attempts):
            limiter.record_attempt(key)

        # Should be rate limited
        assert limiter.is_rate_limited(key, max_attempts, window_seconds)
        assert limiter.get_remaining_attempts(key, max_attempts, window_seconds) == 0

    def test_blocks_above_limit(self, limiter):
        """Should block when exceeding max attempts."""
        key = "test:user:127.0.0.1"
        max_attempts = 3
        window_seconds = 10

        # Record more attempts than limit
        for _ in range(5):
            limiter.record_attempt(key)

        # Should be rate limited
        assert limiter.is_rate_limited(key, max_attempts, window_seconds)

    def test_clears_attempts(self, limiter):
        """Should clear all attempts for a key."""
        key = "test:user:127.0.0.1"
        max_attempts = 3
        window_seconds = 10

        # Record attempts
        for _ in range(max_attempts):
            limiter.record_attempt(key)

        # Verify it's rate limited
        assert limiter.is_rate_limited(key, max_attempts, window_seconds)

        # Clear attempts
        limiter.clear_attempts(key)

        # Should now be below limit
        assert not limiter.is_rate_limited(key, max_attempts, window_seconds)
        assert limiter.get_remaining_attempts(key, max_attempts, window_seconds) == max_attempts

    def test_window_expiration(self, limiter):
        """Should remove attempts outside the time window."""
        key = "test:user:127.0.0.1"
        max_attempts = 2
        window_seconds = 1  # 1 second window

        # Record attempt
        limiter.record_attempt(key)

        # Should not be rate limited with 1 attempt
        assert not limiter.is_rate_limited(key, max_attempts, window_seconds)

        # Wait for window to expire
        time.sleep(1.1)

        # Record another attempt (first one should have expired)
        limiter.record_attempt(key)

        # Should still not be rate limited
        assert not limiter.is_rate_limited(key, max_attempts, window_seconds)

    def test_independent_keys(self, limiter):
        """Different keys should have independent limits."""
        key1 = "test:user1:127.0.0.1"
        key2 = "test:user2:127.0.0.1"
        max_attempts = 2
        window_seconds = 10

        # Fill up key1
        limiter.record_attempt(key1)
        limiter.record_attempt(key1)

        # key1 is at limit
        assert limiter.is_rate_limited(key1, max_attempts, window_seconds)

        # key2 should still be available
        assert not limiter.is_rate_limited(key2, max_attempts, window_seconds)


class TestRateLimiterAPI:
    """Test the public rate limiter API."""

    def test_is_rate_limited_api(self):
        """Test public is_rate_limited function."""
        key = "test:api:key"
        # Should be available initially
        assert rate_limiter_service.get_remaining_attempts(key, 3, 10) == 3

    def test_record_attempt_api(self):
        """Test public record_attempt function."""
        key = "test:record:key"
        rate_limiter_service.record_attempt(key)
        # After 1 attempt, should have 2 remaining
        assert rate_limiter_service.get_remaining_attempts(key, 3, 10) == 2

    def test_clear_attempts_api(self):
        """Test public clear_attempts function."""
        key = "test:clear:key"
        rate_limiter_service.record_attempt(key)
        rate_limiter_service.record_attempt(key)

        # Should have 1 remaining
        assert rate_limiter_service.get_remaining_attempts(key, 3, 10) == 1

        # Clear and check
        rate_limiter_service.clear_attempts(key)
        assert rate_limiter_service.get_remaining_attempts(key, 3, 10) == 3


class TestLoginRateLimit:
    """Test login-specific rate limiting scenarios."""

    def test_login_rate_limit_per_ip_and_user(self):
        """Different IP/user combinations should have independent limits."""
        key1 = "127.0.0.1:admin"
        key2 = "127.0.0.2:admin"
        key3 = "127.0.0.1:user"

        # Exhaust limit for key1
        for _ in range(3):
            rate_limiter_service.record_attempt(key1, window_seconds=300)

        # key1 is blocked
        assert rate_limiter_service.is_rate_limited(key1, 3, 300)

        # key2 and key3 are not blocked
        assert not rate_limiter_service.is_rate_limited(key2, 3, 300)
        assert not rate_limiter_service.is_rate_limited(key3, 3, 300)

    def test_successful_login_clears_attempts(self):
        """Successful login should clear attempts for that IP/user combo."""
        key = "192.168.1.1:testuser"

        # Record some failed attempts
        for _ in range(2):
            rate_limiter_service.record_attempt(key, window_seconds=300)

        # Should have 1 attempt remaining
        assert rate_limiter_service.get_remaining_attempts(key, 3, 300) == 1

        # Simulate successful login (clear attempts)
        rate_limiter_service.clear_attempts(key)

        # Should now have full quota
        assert rate_limiter_service.get_remaining_attempts(key, 3, 300) == 3
