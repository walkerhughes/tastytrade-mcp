"""Structured logging that is safe for stdio MCP servers.

stdout is reserved for the MCP JSON-RPC channel, so all logs go to **stderr**.
Logs are single-line ``key=value`` records to stay greppable without a JSON parser.
"""

import logging
import sys

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
