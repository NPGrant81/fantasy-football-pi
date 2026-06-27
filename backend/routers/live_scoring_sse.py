"""
live_scoring_sse.py

Server-Sent Events (SSE) endpoint for real-time live scoring updates.

GET /live-scoring/stream
  - Streams scoring change events to connected clients.
  - Events are only emitted when the poll cycle detects a scoreboard
    change (downstream_updates_triggered=True), so bandwidth and client
    processing are minimised.
  - A keepalive comment (': keepalive') is sent every 30 s so proxies
    and load balancers do not close idle connections.
  - Clients should use the browser EventSource API or any SSE-compatible
    client.  On reconnect the browser automatically retries.

Event format (application/json, one per data line):
  {
    "event": "score_update",
    "year": 2026,
    "week": 14,
    "active_games": 3,
    "is_active_window": true,
    "state_transitions": [...],
    "scoreboard_fingerprint": "abc123",
    "matchup_projection_snapshots": [...],
    "ts": 1746000000
  }
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/live-scoring", tags=["live-scoring"])

_QUEUE_WAIT_SECONDS = 1
_KEEPALIVE_TIMEOUT_SECONDS = 30
_QUEUE_WAIT_SECONDS = _KEEPALIVE_TIMEOUT_SECONDS


async def _event_stream(q: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings from the client queue indefinitely."""
    idle_seconds = 0
    try:
        # Flush an initial SSE event so clients do not block waiting for first bytes.
        yield "event: connected\ndata: {}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=_QUEUE_WAIT_SECONDS)
                idle_seconds = 0
                payload = json.dumps(event, separators=(",", ":"))
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                idle_seconds += _QUEUE_WAIT_SECONDS
                # Keep the HTTP connection alive through proxies
                if idle_seconds >= _KEEPALIVE_TIMEOUT_SECONDS:
                    yield ": keepalive\n\n"
                    idle_seconds = 0
    except asyncio.CancelledError:
        # Client disconnected.
        return
    finally:
        try:
            from backend.services.live_scoring_event_bus import unsubscribe

            unsubscribe(q)
        except Exception:  # pragma: no cover
            pass


@router.get(
    "/stream",
    summary="SSE stream of live scoring updates",
    description=(
        "Opens a persistent Server-Sent Events connection. "
        "The server pushes a JSON event whenever the live scoring poll "
        "cycle detects a scoreboard change. "
        "Sends a keepalive comment every 30 s to maintain the connection. "
        "Disconnect and reconnect to resume; the browser EventSource API "
        "handles reconnection automatically."
    ),
    response_class=StreamingResponse,
)
async def live_scoring_stream() -> StreamingResponse:
    from backend.services.live_scoring_event_bus import subscribe

    q = subscribe()
    LOGGER.info("live_scoring.sse client_connected")
    return StreamingResponse(
        _event_stream(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
