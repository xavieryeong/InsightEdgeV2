from __future__ import annotations

import random
import time

import anthropic

from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL


_MAX_RETRY_ATTEMPTS = 6
_BASE_DELAY = 2.0
_MAX_DELAY = 60.0
_JITTER_RATIO = 0.3


def safe_create(client, **kwargs):
    """Call ``client.messages.create`` with retry on transient errors.

    Retries on RateLimitError, APIConnectionError, and 5xx APIStatusError.
    Honours the ``retry-after`` header. Exponential backoff with jitter,
    capped at ~60s. Re-raises after exhausting attempts.
    """
    attempt = 0
    while True:
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            attempt += 1
            if attempt >= _MAX_RETRY_ATTEMPTS:
                raise
            time.sleep(_retry_delay(e, attempt))
        except anthropic.APIConnectionError:
            attempt += 1
            if attempt >= _MAX_RETRY_ATTEMPTS:
                raise
            time.sleep(_backoff(attempt))
        except anthropic.APIStatusError as e:
            status = getattr(e, "status_code", None)
            if status is None or status < 500 or status >= 600:
                raise
            attempt += 1
            if attempt >= _MAX_RETRY_ATTEMPTS:
                raise
            time.sleep(_retry_delay(e, attempt))


def _retry_delay(err, attempt: int) -> float:
    response = getattr(err, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers is not None:
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    return min(float(retry_after), _MAX_DELAY)
                except (TypeError, ValueError):
                    pass
    return _backoff(attempt)


def _backoff(attempt: int) -> float:
    base = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
    jitter = base * _JITTER_RATIO * (2 * random.random() - 1)
    return max(0.0, base + jitter)


class BaseAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = CLAUDE_MODEL

    def ask_claude(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        """Return ``(text, usage)`` where usage is ``{"input": int, "output": int}``."""
        response = safe_create(
            self.client,
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return (
            response.content[0].text,
            {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        )
