"""Shared state and helpers for tool modules: client, cache, account resolution."""

import json
from typing import Awaitable, Callable

from ..client import TastyTradeClient
from ..config import get_settings
from ..infra.cache import TTLCache


def fmt(data: object) -> str:
    """Render a tool result as compact, stable JSON."""
    return json.dumps(data, indent=2, default=str)


def items(resp: dict) -> list:
    """Extract the item list from Tastytrade's response envelope."""
    data = resp.get("data", resp)
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    return [data]


_client: TastyTradeClient | None = None
_cache: TTLCache | None = None


def get_client() -> TastyTradeClient:
    """Lazy-init the API client so env vars are read at runtime, not import time."""
    global _client
    if _client is None:
        _client = TastyTradeClient()
    return _client


def get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(max_keys=get_settings().cache_max_keys)
    return _cache


def reset_state() -> None:
    """Test hook: drop the client and cache singletons."""
    global _client, _cache
    _client = None
    _cache = None


async def resolve_account(account_number: str) -> str:
    """Use the provided account number or fall back to the default (first) account."""
    if account_number:
        return account_number
    return await get_client().get_default_account_number()


async def cached_fetch(resource: str, key: str, fetch: Callable[..., Awaitable[dict]]) -> dict:
    """Return a cached response for ``key`` or fetch+store it using the resource's TTL.

    ``resource`` selects the TTL from settings; an unknown resource (or ttl<=0) means
    no caching (e.g. live orders).
    """
    ttls = get_settings().cache_ttls
    ttl = ttls.get(resource, 0)
    cache = get_cache()
    cache_key = f"{resource}:{key}"
    if ttl > 0:
        hit = cache.get(cache_key)
        if hit is not None:
            return hit
    data = await fetch()
    if ttl > 0:
        cache.set(cache_key, data, ttl)
    return data
