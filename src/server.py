"""
Tastytrade MCP Server
---------------------
Exposes the Tastytrade SDK as MCP tools for use in Claude Code.

Environment variables (set in .env, loaded via mcp.json):
    OAuth2 (preferred):
        TT_CLIENT_ID     - Your OAuth2 client ID
        TT_SECRET        - Your OAuth2 client secret
        TT_REFRESH       - Your OAuth2 refresh token
        API_BASE_URL     - Optional: defaults to api.tastyworks.com

    Legacy (fallback):
        TT_USERNAME      - Your Tastytrade username
        TT_PASSWORD      - Your Tastytrade password
"""

import json
import os
import threading
import warnings
from typing import Any

from mcp.server.fastmcp import FastMCP
from tastytrade_sdk import Tastytrade

# ---------------------------------------------------------------------------
# Bootstrap SDK (lazy singleton — auth happens once at first tool call)
# ---------------------------------------------------------------------------

_tasty: Tastytrade | None = None
_lock = threading.Lock()


def _get_client() -> Tastytrade:
    global _tasty
    if _tasty is None:
        with _lock:
            if _tasty is None:
                base_url = os.environ.get("API_BASE_URL", "api.tastyworks.com")
                client_id = os.environ.get("TT_CLIENT_ID")
                client_secret = os.environ.get("TT_SECRET")
                refresh_token = os.environ.get("TT_REFRESH")

                if client_id and client_secret and refresh_token:
                    _tasty = Tastytrade(
                        api_base_url=base_url,
                        client_id=client_id,
                        client_secret=client_secret,
                        refresh_token=refresh_token,
                    )
                else:
                    username = os.environ["TT_USERNAME"]
                    password = os.environ["TT_PASSWORD"]
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", DeprecationWarning)
                        _tasty = Tastytrade(api_base_url=base_url).login(username, password)
    return _tasty


def _reset_client() -> None:
    """Reset the singleton (used in tests)."""
    global _tasty
    _tasty = None


def _unwrap(data: Any) -> Any:
    """Extract the 'data' envelope the Tastytrade API wraps responses in."""
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def _json(data: Any) -> str:
    return json.dumps(_unwrap(data), indent=2, default=str)


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("tastytrade")


# ── Account tools ────────────────────────────────────────────────────────────


@mcp.tool()
def get_accounts() -> str:
    """List all Tastytrade accounts associated with the authenticated user.
    Returns account numbers, types, and basic metadata."""
    try:
        result = _get_client().api.get("/customers/me/accounts")
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


@mcp.tool()
def get_balances(account_number: str) -> str:
    """Get account balances including net liquidating value, cash balance, and buying power."""
    try:
        result = _get_client().api.get(f"/accounts/{account_number}/balances")
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


@mcp.tool()
def get_positions(account_number: str) -> str:
    """Get all open positions for an account."""
    try:
        result = _get_client().api.get(f"/accounts/{account_number}/positions")
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


# ── Orders ───────────────────────────────────────────────────────────────────


@mcp.tool()
def get_live_orders(account_number: str) -> str:
    """Get all live (open/working) orders for an account."""
    try:
        result = _get_client().api.get(f"/accounts/{account_number}/orders/live")
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


@mcp.tool()
def get_order_history(
    account_number: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get historical orders for an account. Optionally filter by date range (ISO 8601, e.g. 2024-01-01)."""
    try:
        params: dict[str, str] = {}
        if start_date:
            params["start-date"] = start_date
        if end_date:
            params["end-date"] = end_date
        result = _get_client().api.get(
            f"/accounts/{account_number}/orders",
            params=params or None,
        )
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


# ── Instruments ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_equity_info(symbols: list[str]) -> str:
    """Get instrument details for one or more equity symbols (stocks/ETFs)."""
    try:
        params = [("symbol[]", s) for s in symbols]
        result = _get_client().api.get("/instruments/equities", params=params)
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


@mcp.tool()
def get_option_chain(symbol: str) -> str:
    """Get the option chain for an underlying symbol. Returns available expirations and strikes."""
    try:
        result = _get_client().api.get(f"/option-chains/{symbol}/nested")
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


# ── Market data ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_quotes(symbols: list[str]) -> str:
    """Get current price quotes for one or more equity/index symbols.
    Examples: symbols=["AAPL","SPY","SPX"]."""
    try:
        params = [("symbols", s) for s in symbols]
        result = _get_client().api.get("/market-metrics", params=params)
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


@mcp.tool()
def get_market_metrics(symbols: list[str]) -> str:
    """Get market metrics (IV rank, IV percentile, liquidity rating, beta, etc.) for one or more symbols."""
    try:
        params = [("symbols", s) for s in symbols]
        result = _get_client().api.get("/market-metrics", params=params)
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


# ── Generic escape hatch ────────────────────────────────────────────────────


@mcp.tool()
def tastytrade_api_request(
    method: str,
    path: str,
    params: dict | None = None,
    data: dict | None = None,
) -> str:
    """ADVANCED: Make a raw request to any Tastytrade API endpoint.
    Use this only when no specific tool covers the endpoint you need.
    Consult https://developer.tastytrade.com for available paths."""
    try:
        api = _get_client().api
        m = method.upper()
        dispatch: dict[str, Any] = {
            "GET": lambda: api.get(path, params=params),
            "POST": lambda: api.post(path, params=params, data=data),
            "PUT": lambda: api.put(path, params=params, data=data),
            "PATCH": lambda: api.patch(path, params=params, data=data),
            "DELETE": lambda: api.delete(path, params=params),
        }
        fn = dispatch.get(m)
        if fn is None:
            return _error(f"Unknown method: {method}")
        result = fn()
        return _json(result)
    except BaseException as e:
        return _error(f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run()


if __name__ == "__main__":
    main()
