import anthropic

from bot.config import settings

_client: anthropic.AsyncAnthropic | None = None


def get_claude_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def parse_deadline(natural_language: str) -> str:
    """Return an ISO 8601 datetime string parsed from natural language."""
    client = get_claude_client()
    message = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract the deadline from this text and return ONLY an ISO 8601 datetime "
                    f"(e.g. 2025-01-15T09:00:00). Text: {natural_language}"
                ),
            }
        ],
    )
    from bot.shared.exceptions import DeadlineParseError

    if not message.content or not hasattr(message.content[0], "text"):
        raise DeadlineParseError("Claude returned no text content")
    return message.content[0].text.strip()
