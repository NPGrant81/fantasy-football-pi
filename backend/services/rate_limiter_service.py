"""
Distributed rate limiting service with Redis backend and in-memory fallback.

Provides rate-limiting primitives for security-sensitive operations (auth, API).
Supports both Redis (for distributed deployments) and in-memory (for single-instance/testing).
"""

import logging
import os
import time
import threading
from collections import defaultdict, deque
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Configuration from environment
RATE_LIMITER_BACKEND = os.getenv("RATE_LIMITER_BACKEND", "memory")  # "redis" or "memory"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_POOL_SIZE = int(os.getenv("REDIS_POOL_SIZE", "10"))


class RateLimiterBackend:
    """Base rate limiter interface."""

    def is_rate_limited(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Check if key has exceeded rate limit."""
        raise NotImplementedError

    def record_attempt(self, key: str, window_seconds: int = 3600) -> None:
        """Record an attempt for the given key."""
        raise NotImplementedError

    def clear_attempts(self, key: str) -> None:
        """Clear all attempts for the given key."""
        raise NotImplementedError

    def get_remaining_attempts(self, key: str, max_attempts: int, window_seconds: int) -> int:
        """Get remaining attempts before rate limit is hit."""
        raise NotImplementedError

    def cleanup_expired(self, window_seconds: int) -> None:
        """Clean up expired entries (optional, for housekeeping)."""
        pass


class InMemoryRateLimiter(RateLimiterBackend):
    """In-memory rate limiter using thread-safe deque (single-instance)."""

    def __init__(self):
        self.failed_attempts: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim_old_attempts(self, attempts: deque, now: float, window_seconds: int) -> None:
        """Remove attempts outside the time window."""
        cutoff = now - window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.popleft()

    def is_rate_limited(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Check if key has exceeded rate limit."""
        now = time.monotonic()
        with self._lock:
            attempts = self.failed_attempts[key]
            self._trim_old_attempts(attempts, now, window_seconds)
            return len(attempts) >= max_attempts

    def record_attempt(self, key: str, window_seconds: int = 3600) -> None:
        """Record an attempt for the given key."""
        now = time.monotonic()
        with self._lock:
            attempts = self.failed_attempts[key]
            self._trim_old_attempts(attempts, now, window_seconds)
            attempts.append(now)

    def clear_attempts(self, key: str) -> None:
        """Clear all attempts for the given key."""
        with self._lock:
            self.failed_attempts.pop(key, None)

    def get_remaining_attempts(self, key: str, max_attempts: int, window_seconds: int) -> int:
        """Get remaining attempts before rate limit is hit."""
        now = time.monotonic()
        with self._lock:
            attempts = self.failed_attempts[key]
            self._trim_old_attempts(attempts, now, window_seconds)
            return max(0, max_attempts - len(attempts))


class RedisRateLimiter(RateLimiterBackend):
    """Redis-backed rate limiter for distributed deployments."""

    def __init__(self):
        self.client = None
        self._fallback = InMemoryRateLimiter()
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Lazily initialize Redis client on first use."""
        try:
            import redis
            from redis.connection import ConnectionPool

            # Use connection pool for efficiency
            pool = ConnectionPool.from_url(REDIS_URL, max_connections=REDIS_POOL_SIZE)
            self.client = redis.Redis(connection_pool=pool)

            # Test connection
            self.client.ping()
            logger.info("Redis rate limiter initialized successfully")
        except Exception as e:
            logger.warning(
                "Redis connection failed; falling back to in-memory (error=%s)",
                e.__class__.__name__,
            )
            self.client = None

    def is_rate_limited(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Check if key has exceeded rate limit."""
        if not self.client:
            return self._fallback.is_rate_limited(key, max_attempts, window_seconds)

        try:
            current_count = self.client.get(key)
            count = int(current_count) if current_count else 0
            return count >= max_attempts
        except Exception as exc:
            logger.warning(
                "Redis check failed for key=%s; using in-memory fallback (error=%s)",
                key,
                exc.__class__.__name__,
            )
            return self._fallback.is_rate_limited(key, max_attempts, window_seconds)

    def record_attempt(self, key: str, window_seconds: int = 3600) -> None:
        """Record an attempt for the given key."""
        if not self.client:
            self._fallback.record_attempt(key, window_seconds)
            return

        try:
            # Increment counter and set expiration
            pipe = self.client.pipeline()
            pipe.incr(key)
            # Only set TTL when the key is first created.
            pipe.expire(key, window_seconds, nx=True)
            pipe.execute()
        except Exception as exc:
            logger.warning(
                "Redis record failed for key=%s; using in-memory fallback (error=%s)",
                key,
                exc.__class__.__name__,
            )
            self._fallback.record_attempt(key, window_seconds)

    def clear_attempts(self, key: str) -> None:
        """Clear all attempts for the given key."""
        if not self.client:
            self._fallback.clear_attempts(key)
            return

        try:
            self.client.delete(key)
        except Exception as exc:
            logger.warning(
                "Redis clear failed for key=%s; clearing in-memory fallback (error=%s)",
                key,
                exc.__class__.__name__,
            )
            self._fallback.clear_attempts(key)

    def get_remaining_attempts(self, key: str, max_attempts: int, window_seconds: int) -> int:
        """Get remaining attempts before rate limit is hit."""
        if not self.client:
            return self._fallback.get_remaining_attempts(key, max_attempts, window_seconds)

        try:
            current_count = self.client.get(key)
            count = int(current_count) if current_count else 0
            return max(0, max_attempts - count)
        except Exception as exc:
            logger.warning(
                "Redis get_remaining failed for key=%s; using in-memory fallback (error=%s)",
                key,
                exc.__class__.__name__,
            )
            return self._fallback.get_remaining_attempts(key, max_attempts, window_seconds)

    def cleanup_expired(self, window_seconds: int) -> None:
        """Redis keys auto-expire via TTL; no manual cleanup needed."""
        pass


# Global rate limiter instance
_rate_limiter: Optional[RateLimiterBackend] = None


def get_rate_limiter() -> RateLimiterBackend:
    """Get or initialize the global rate limiter."""
    global _rate_limiter

    if _rate_limiter is None:
        if RATE_LIMITER_BACKEND == "redis":
            _rate_limiter = RedisRateLimiter()
            # If Redis failed to initialize, fall back to in-memory
            if isinstance(_rate_limiter, RedisRateLimiter) and _rate_limiter.client is None:
                logger.warning("Redis rate limiter unavailable; using in-memory fallback")
                _rate_limiter = InMemoryRateLimiter()
        else:
            _rate_limiter = InMemoryRateLimiter()

    return _rate_limiter


# Public API
def is_rate_limited(key: str, max_attempts: int, window_seconds: int) -> bool:
    """Check if a rate limit key has exceeded its quota."""
    limiter = get_rate_limiter()
    return limiter.is_rate_limited(key, max_attempts, window_seconds)


def record_attempt(key: str, window_seconds: int = 3600) -> None:
    """Record an attempt for the given rate limit key."""
    limiter = get_rate_limiter()
    limiter.record_attempt(key, window_seconds)


def clear_attempts(key: str) -> None:
    """Clear all attempts for a given rate limit key."""
    limiter = get_rate_limiter()
    limiter.clear_attempts(key)


def get_remaining_attempts(key: str, max_attempts: int, window_seconds: int) -> int:
    """Get the number of remaining attempts before rate limit is hit."""
    limiter = get_rate_limiter()
    return limiter.get_remaining_attempts(key, max_attempts, window_seconds)
