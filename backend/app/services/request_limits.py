from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException


_requests: OrderedDict[tuple[str, int, int], deque] = OrderedDict()
_lock = Lock()


def enforce_request_limit(scope: str, db, user_id: int, limit: int):
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    key = (scope, id(engine), int(user_id))
    now = monotonic()
    with _lock:
        queue = _requests.setdefault(key, deque())
        while queue and queue[0] <= now - 60:
            queue.popleft()
        if len(queue) >= limit:
            retry_after = max(1, ceil(queue[0] + 60 - now))
            raise HTTPException(429, "Too many requests. Please wait and retry.",
                                headers={"Retry-After": str(retry_after)})
        queue.append(now)
        _requests.move_to_end(key)
        while len(_requests) > 4096:
            _requests.popitem(last=False)
