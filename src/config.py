"""Runtime configuration for the Tastytrade MCP server.

All settings are read from the environment so behavior can be tuned per-deployment
without code changes. Trading is OFF by default — placing live orders requires an
explicit operator opt-in (``TT_ENABLE_TRADING``) in addition to a per-call ``confirm``.
"""

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Per-resource cache TTLs in seconds. Live orders are intentionally absent (never cached).
DEFAULT_CACHE_TTLS: dict[str, int] = {
    "quotes": 15,
    "market_metrics": 120,
    "transactions": 300,
    "option_chain": 300,
    "accounts": 900,
    "instruments": 900,
    "watchlists": 900,
}


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of environment-derived settings."""

    enable_trading: bool
    log_level: str
    cache_max_keys: int
    cache_ttls: dict[str, int]

    @classmethod
    def from_env(cls) -> "Settings":
        ttls = dict(DEFAULT_CACHE_TTLS)
        # Allow overriding any TTL via TT_CACHE_TTL_<RESOURCE> (e.g. TT_CACHE_TTL_QUOTES=30)
        for resource in list(ttls):
            ttls[resource] = _int_env(f"TT_CACHE_TTL_{resource.upper()}", ttls[resource])
        return cls(
            enable_trading=_bool_env("TT_ENABLE_TRADING", default=False),
            log_level=os.environ.get("TT_LOG_LEVEL", "INFO").upper(),
            cache_max_keys=_int_env("TT_CACHE_MAX_KEYS", 1000),
            cache_ttls=ttls,
        )


def get_settings() -> Settings:
    """Read settings fresh from the environment (cheap; called at tool time)."""
    return Settings.from_env()
