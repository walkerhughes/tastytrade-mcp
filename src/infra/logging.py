"""Structured logging that is safe for stdio MCP servers.

stdout is reserved for the MCP JSON-RPC channel, so all logs go to **stderr**.
Logs are single-line ``key=value`` records to stay greppable without a JSON parser.
"""

import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Install a stderr handler once. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        logging.getLogger("tastytrade_mcp").setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger = logging.getLogger("tastytrade_mcp")
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    _CONFIGURED = True


def get_logger() -> logging.Logger:
    return logging.getLogger("tastytrade_mcp")


def _kv(fields: dict[str, object]) -> str:
    return " ".join(f"{k}={v}" for k, v in fields.items())


@contextmanager
def log_tool_call(tool: str, **fields: object) -> Iterator[dict[str, object]]:
    """Time a tool call and emit a structured record. Extra fields can be set on the
    yielded dict (e.g. ``rec["cache"] = "hit"``, ``rec["bytes"] = len(out)``)."""
    log = get_logger()
    rec: dict[str, object] = dict(fields)
    start = time.monotonic()
    log.debug("tool_start %s", _kv({"tool": tool, **rec}))
    try:
        yield rec
    except Exception as exc:  # logged then re-raised; @guarded_tool shapes the response
        dur_ms = round((time.monotonic() - start) * 1000, 1)
        log.warning("tool_error %s", _kv({"tool": tool, "ms": dur_ms, "err": type(exc).__name__, **rec}))
        raise
    else:
        dur_ms = round((time.monotonic() - start) * 1000, 1)
        log.info("tool_ok %s", _kv({"tool": tool, "ms": dur_ms, **rec}))
