import asyncio
from datetime import UTC, datetime

import anthropic
from dateutil import parser as dateutil_parser

from bot.config import settings
from bot.shared.exceptions import DeadlineParseError

_PARSE_TIMEOUT = 4.0

_client: anthropic.AsyncAnthropic | None = None


def get_claude_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def parse_deadline(natural_language: str) -> datetime | None:
    """Return a tz-aware UTC datetime parsed from natural language, or None if unresolvable.

    Raises DeadlineParseError on unexpected API errors (empty content).
    Times out after 4 s and returns None.
    """
    client = get_claude_client()
    try:
        message = await asyncio.wait_for(
            client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=64,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Extract the deadline from this text and return ONLY an ISO 8601 "
                            "datetime (e.g. 2025-01-15T09:00:00+00:00). "
                            "If you cannot determine a specific date and time, reply with exactly "
                            "the word NONE. Text: " + natural_language
                        ),
                    }
                ],
            ),
            timeout=_PARSE_TIMEOUT,
        )
    except TimeoutError:
        return None

    if not message.content:
        raise DeadlineParseError("Claude returned no content")

    first = message.content[0]
    if not hasattr(first, "text"):
        raise DeadlineParseError(f"Unexpected content block type: {type(first)}")

    text = first.text.strip()  # type: ignore[union-attr]
    if text.upper() == "NONE":
        return None

    try:
        dt = dateutil_parser.parse(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, OverflowError):
        return None
