"""Tiny in-memory circuit breaker for the OpenAI API.

When a call fails (no credits, auth, connection), we 'trip' the breaker for a while
so subsequent `available()` checks return False immediately instead of every call
eating its full timeout. Keeps the app responsive when the API is down/out of credits
— matching/search/review just degrade to local fuzzy."""
from __future__ import annotations

import time

_until = 0.0
_TTL = 120.0  # seconds the breaker stays open after a failure


def trip() -> None:
    global _until
    _until = time.monotonic() + _TTL


def is_open() -> bool:
    """True while the breaker is open (skip OpenAI calls)."""
    return time.monotonic() < _until
