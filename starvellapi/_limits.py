from __future__ import annotations

import asyncio
import re
import time
from collections import deque

_sleep = asyncio.sleep
_now = time.monotonic

# лимиты из документации Starvell (запросов за 60 секунд на пользователя), для остального - свои с запасом
LIMITS: dict[str, tuple[int, float]] = {
    "messages_send": (60, 60),
    "messages_list": (60, 60),
    "chats": (90, 60),
    "offers_update": (25, 60),
    "offers_partial_update": (100, 60),
    "orders_list": (30, 60),
    "default": (60, 60),
}

_GROUPS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/api/messages/send"), "messages_send"),
    (re.compile(r"^/api/messages/list"), "messages_list"),
    (re.compile(r"^/api/chats/(list|list-pinned|list-open-order)$"), "chats"),
    (re.compile(r"^/api/offers/[^/]+/update$"), "offers_update"),
    (re.compile(r"^/api/offers/[^/]+/partial-update$"), "offers_partial_update"),
    (re.compile(r"^/api/orders/list$"), "orders_list"),
]


def group_of(path: str) -> str:
    for pattern, group in _GROUPS:
        if pattern.search(path):
            return group
    return "default"


class _Window:
    def __init__(self, limit: int, period: float):
        self.limit = limit
        self.period = period
        self.calls: deque[float] = deque()

    def delay(self) -> float:
        now = _now()
        while self.calls and now - self.calls[0] >= self.period:
            self.calls.popleft()
        if len(self.calls) < self.limit:
            self.calls.append(now)
            return 0.0
        return self.calls[0] + self.period - now


class RateLimiter:
    def __init__(self, limits: dict[str, tuple[int, float]] | None = None):
        self.limits = {**LIMITS, **(limits or {})}
        self._windows: dict[str, _Window] = {}

    async def acquire(self, path: str):
        group = group_of(path)
        window = self._windows.get(group)
        if window is None:
            limit, period = self.limits.get(group, self.limits["default"])
            window = self._windows[group] = _Window(limit, period)
        while True:
            # без await между проверкой и записью - в одном loop это атомарно
            delay = window.delay()
            if delay <= 0:
                return
            await _sleep(delay)
