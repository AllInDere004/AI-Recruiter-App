"""Bounded per-user AI request budget for a single backend process.

Deployment with multiple workers needs a shared limiter. Keys contain only the
database-engine object's identity and the verified integer user ID; no text,
credentials, or tokens are stored or logged.
"""
from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException

from app.config import settings


WINDOW_SECONDS = 60
MAX_TRACKED_USERS = 2048
_usage = OrderedDict()
_lock = Lock()


def enforce_ai_usage(db, user_id: int):
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    key = (id(engine), int(user_id))
    now = monotonic()
    with _lock:
        history = _usage.setdefault(key, deque())
        while history and history[0] <= now - WINDOW_SECONDS:
            history.popleft()
        if len(history) >= settings.AI_REQUESTS_PER_MINUTE:
            retry_after = max(1, ceil(history[0] + WINDOW_SECONDS - now))
            raise HTTPException(429, "Too many AI requests. Please wait and retry.",
                                headers={"Retry-After": str(retry_after)})
        history.append(now)
        _usage.move_to_end(key)
        while len(_usage) > MAX_TRACKED_USERS:
            _usage.popitem(last=False)
