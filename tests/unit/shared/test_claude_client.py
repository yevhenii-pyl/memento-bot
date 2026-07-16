"""T05 unit tests — Claude deadline parser."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.shared.claude_client import parse_deadline
from bot.shared.exceptions import DeadlineParseError


async def _make_mock_response(text: str):
    content = MagicMock()
    content.text = text
    response = MagicMock()
    response.content = [content]
    return response


@patch("bot.shared.claude_client.get_claude_client")
async def test_parse_deadline_returns_utc_datetime(mock_get_client):
    iso = "2026-08-01T14:00:00+00:00"
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=await _make_mock_response(iso))
    mock_get_client.return_value = mock_client

    result = await parse_deadline("by August 1st 2pm UTC")
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result == datetime(2026, 8, 1, 14, 0, 0, tzinfo=UTC)


@patch("bot.shared.claude_client.get_claude_client")
async def test_parse_deadline_returns_none_for_unresolvable(mock_get_client):
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=await _make_mock_response("NONE"))
    mock_get_client.return_value = mock_client

    result = await parse_deadline("some gibberish text without any deadline")
    assert result is None


@patch("bot.shared.claude_client.get_claude_client")
async def test_parse_deadline_timeout(mock_get_client):
    import asyncio

    mock_client = MagicMock()

    async def slow_create(*args, **kwargs):
        await asyncio.sleep(10)

    mock_client.messages.create = slow_create
    mock_get_client.return_value = mock_client

    result = await parse_deadline("sometime next week")
    assert result is None


@patch("bot.shared.claude_client.get_claude_client")
async def test_parse_deadline_raises_on_empty_content(mock_get_client):
    mock_client = MagicMock()
    response = MagicMock()
    response.content = []
    mock_client.messages.create = AsyncMock(return_value=response)
    mock_get_client.return_value = mock_client

    with pytest.raises(DeadlineParseError):
        await parse_deadline("valid deadline text")


@patch("bot.shared.claude_client.get_claude_client")
async def test_parse_deadline_includes_timezone_in_prompt(mock_get_client):
    """F5: MASTER_TIMEZONE must be anchored in the Claude prompt."""
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.extend(kwargs.get("messages", []))
        return await _make_mock_response("2026-08-01T09:00:00+02:00")

    mock_client = MagicMock()
    mock_client.messages.create = capture
    mock_get_client.return_value = mock_client

    await parse_deadline("by 9am", timezone="Europe/Kyiv")

    assert captured, "messages.create was never called"
    prompt_text = " ".join(str(m) for m in captured)
    assert "Europe/Kyiv" in prompt_text


@patch("bot.shared.claude_client.get_claude_client")
async def test_parse_deadline_naive_datetime_uses_given_timezone(mock_get_client):
    """F5: a naive datetime from Claude must be interpreted in the given timezone, not UTC."""
    from zoneinfo import ZoneInfo

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=await _make_mock_response("2026-08-01T09:00:00")
    )
    mock_get_client.return_value = mock_client

    result = await parse_deadline("by 9am", timezone="America/New_York")
    assert result is not None
    eastern = ZoneInfo("America/New_York")
    expected = datetime(2026, 8, 1, 9, 0, 0, tzinfo=eastern).astimezone(UTC)
    assert result == expected
