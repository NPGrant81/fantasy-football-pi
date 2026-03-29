from datetime import datetime, timedelta, UTC

import pytest
from fastapi import HTTPException

from backend.services.commissioner_deadline_service import (
    enforce_commissioner_deadline,
    parse_commissioner_deadline,
)


def test_parse_commissioner_deadline_none_or_blank():
    assert parse_commissioner_deadline(None) is None
    assert parse_commissioner_deadline("   ") is None


def test_parse_commissioner_deadline_invalid_format_returns_none():
    assert parse_commissioner_deadline("Wed 11PM") is None


def test_enforce_commissioner_deadline_allows_future_deadline():
    now = datetime.now(UTC)
    future_deadline = (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z")

    enforce_commissioner_deadline(
        deadline_value=future_deadline,
        closed_message_prefix="Trade proposals are closed by commissioner rule",
        now=now,
    )


def test_enforce_commissioner_deadline_blocks_past_deadline():
    now = datetime.now(UTC)
    past_deadline = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")

    with pytest.raises(HTTPException) as exc:
        enforce_commissioner_deadline(
            deadline_value=past_deadline,
            closed_message_prefix="Waiver claims are closed by commissioner rule",
            now=now,
        )

    assert exc.value.status_code == 400
    assert "Waiver claims are closed by commissioner rule" in str(exc.value.detail)


def test_enforce_commissioner_deadline_tolerates_invalid_format_with_warning(caplog):
    enforce_commissioner_deadline(
        deadline_value="Wed 11PM",
        closed_message_prefix="Trade proposals are closed by commissioner rule",
    )

    assert any("commissioner deadline parse bypass" in message for message in caplog.messages)
