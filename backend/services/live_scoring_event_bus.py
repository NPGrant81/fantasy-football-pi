"""
live_scoring_event_bus.py

In-memory pub/sub bridge between the APScheduler background poll thread
and connected SSE clients (asyncio).

Design:
- Each SSE client subscribes → receives an asyncio.Queue.
- The background poll thread calls publish_from_thread() when a score
  change is detected; the event is forwarded to every subscribed queue
  via asyncio.run_coroutine_threadsafe so it is safe to call from any
  thread.
- The event loop reference is stored at FastAPI startup via
  set_event_loop(); if it is not set (e.g. in unit tests) the publish
  is a no-op.
"""

import asyncio
import logging
import threading
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

# Maximum number of items allowed in each client queue.
# If the client is slow the oldest items are dropped so the queue does
# not grow without bound.
_QUEUE_MAXSIZE = 50

_lock = threading.Lock()
_clients: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


# ---------------------------------------------------------------------------
# Loop registration (called once at application startup)
# ---------------------------------------------------------------------------


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store a reference to the running asyncio event loop.

    Must be called from inside the loop (e.g. in a FastAPI lifespan
    startup hook) so that background threads can safely schedule
    coroutines onto it.
    """
    global _loop
    _loop = loop
    LOGGER.debug("live_scoring.event_bus loop_registered")


def get_client_count() -> int:
    """Return the number of currently connected SSE clients."""
    with _lock:
        return len(_clients)


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------


def subscribe() -> asyncio.Queue:
    """Register a new SSE client and return its dedicated queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    with _lock:
        _clients.add(q)
    LOGGER.debug("live_scoring.event_bus client_subscribed total=%s", len(_clients))
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove the client queue (called when the SSE connection closes)."""
    with _lock:
        _clients.discard(q)
    LOGGER.debug("live_scoring.event_bus client_unsubscribed total=%s", len(_clients))


# ---------------------------------------------------------------------------
# Publishing (thread-safe)
# ---------------------------------------------------------------------------


def publish_from_thread(event: dict[str, Any]) -> None:
    """Publish a scoring event to all connected SSE clients.

    Safe to call from any thread (e.g. APScheduler background job).
    Events are dropped silently if no loop is registered or no clients
    are connected.
    """
    with _lock:
        clients = list(_clients)

    if not clients:
        return

    loop = _loop
    if loop is None or loop.is_closed():
        LOGGER.debug(
            "live_scoring.event_bus no_loop_available clients=%s event_dropped",
            len(clients),
        )
        return

    dropped = 0
    for q in clients:
        try:
            asyncio.run_coroutine_threadsafe(_put(q, event), loop)
        except Exception as exc:  # pragma: no cover
            dropped += 1
            LOGGER.debug("live_scoring.event_bus publish_error err=%s", exc)

    LOGGER.debug(
        "live_scoring.event_bus published clients=%s dropped=%s",
        len(clients) - dropped,
        dropped,
    )


async def _put(q: asyncio.Queue, event: dict[str, Any]) -> None:
    """Put an event onto a queue, discarding the oldest item if full."""
    if q.full():
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await q.put(event)


# ---------------------------------------------------------------------------
# Test / admin helper
# ---------------------------------------------------------------------------


def build_score_update_event(
    *,
    year: int,
    week: int,
    active_games: int,
    is_active_window: bool,
    state_transitions: list,
    scoreboard_fingerprint: str | None,
    matchup_projection_snapshots: list | None,
) -> dict[str, Any]:
    """Return a standardised event dict for a scoring change cycle."""
    return {
        "event": "score_update",
        "year": year,
        "week": week,
        "active_games": active_games,
        "is_active_window": is_active_window,
        "state_transitions": state_transitions,
        "scoreboard_fingerprint": scoreboard_fingerprint,
        "matchup_projection_snapshots": matchup_projection_snapshots or [],
        "ts": int(time.time()),
    }
