"""TTL + LRU cache, and a cached collection that serves pagination/search/sort locally.

Mirrors Honeycomb's per-resource TTL caches and ``accessCollection``: once a list has
been fetched it can be paged, searched, and sorted entirely from memory, so an agent
clicking through pages never re-hits the upstream API.
"""

import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class TTLCache:
    """Simple in-process TTL cache with an LRU cap. Single-process, async-safe enough
    for our use (no awaits between read and write)."""

    def __init__(self, max_keys: int = 1000, clock: Callable[[], float] = time.monotonic) -> None:
        self._max_keys = max_keys
        self._clock = clock
        self._store: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()

    def get(self, key: Hashable) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: Hashable, value: Any, ttl: float) -> None:
        if ttl <= 0:
            return  # ttl<=0 means "do not cache" (e.g. live orders)
        self._store[key] = (self._clock() + ttl, value)
        self._store.move_to_end(key)
        while len(self._store) > self._max_keys:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


def access_collection(
    items: list[dict],
    *,
    page: int = 1,
    limit: int = 25,
    sort_by: str = "",
    sort_order: str = "desc",
    search: str = "",
    search_fields: list[str] | None = None,
) -> dict:
    """Page/search/sort a list of dicts in memory. Returns the page plus pagination meta.

    Mirrors Honeycomb's cache-backed collection access so repeated paging is free.
    """
    rows = items

    if search:
        needle = search.lower()
        fields = search_fields
        rows = [r for r in rows if _row_matches(r, needle, fields)]

    if sort_by:
        rows = sorted(rows, key=lambda r: _sort_key(r.get(sort_by)), reverse=(sort_order != "asc"))

    total = len(rows)
    limit = max(1, limit)
    page = max(1, page)
    start = (page - 1) * limit
    page_rows = rows[start : start + limit]
    total_pages = (total + limit - 1) // limit if total else 0

    return {
        "items": page_rows,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
        },
    }


def _row_matches(row: dict, needle: str, fields: list[str] | None) -> bool:
    if fields:
        values = [row.get(f) for f in fields]
    else:
        values = list(row.values())
    return any(needle in str(v).lower() for v in values if v is not None)


def _sort_key(value: object) -> tuple[int, object]:
    """Sort numbers before strings; None sorts last. Returns a comparable tuple."""
    if value is None:
        return (2, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, float(value))
    try:
        return (0, float(str(value)))
    except (ValueError, TypeError):
        return (1, str(value).lower())
