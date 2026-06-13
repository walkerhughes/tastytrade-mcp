"""Account, portfolio, and portfolio-history tools."""

from mcp.server.fastmcp import FastMCP

from ..infra.errors import guarded_tool
from ..shaping.portfolio import shape_history, shape_portfolio
from .base import cached_fetch, fmt, get_client, items, resolve_account


@guarded_tool
async def list_accounts() -> str:
    """List trading accounts with their numbers, types, and options-trading status.

    Start here to discover account numbers, then pass them to the other tools (or omit
    account_number to use the first account).
    """
    client = get_client()
    accounts = await cached_fetch("accounts", "list", lambda: client.get("/customers/me/accounts"))
    account_items = items(accounts)
    results = []
    for item in account_items:
        acct = item.get("account", item)
        num = acct.get("account-number")
        status = {}
        if num:
            try:
                raw = await cached_fetch(
                    "accounts", f"status:{num}", lambda n=num: client.get(f"/accounts/{n}/trading-status")
                )
                sd = raw.get("data", raw)
                status = {
                    "options_level": sd.get("options-level"),
                    "day_trade_count": sd.get("day-trade-count"),
                    "is_frozen": sd.get("is-frozen"),
                    "is_closed": sd.get("is-closed-positions-only") or acct.get("is-closed"),
                }
            except Exception:
                status = {}
        results.append(
            {
                "account_number": num,
                "account_type": acct.get("account-type-name") or acct.get("account-type"),
                "nickname": acct.get("nickname", ""),
                "margin_or_cash": acct.get("margin-or-cash"),
                **status,
            }
        )
    return fmt(results)


@guarded_tool
async def get_portfolio(account_number: str = "", include_closed: bool = False) -> str:
    """Get balances and positions together with a P/L rollup summary.

    Returns net liq, buying power, each position's market value and unrealized P/L, and a
    `summary` with total P/L and exposure by underlying. This answers "how am I doing?" in
    one call.

    Args:
        account_number: Account number; empty uses the default account.
        include_closed: Include fully-closed positions.
    """
    client = get_client()
    acct = await resolve_account(account_number)
    balances_resp = await cached_fetch("accounts", f"balances:{acct}", lambda: client.get(f"/accounts/{acct}/balances"))
    params = {"include-marks": "true", "include-closed-positions": str(include_closed).lower()}
    positions_resp = await client.get(f"/accounts/{acct}/positions", params=params)
    balances = balances_resp.get("data", balances_resp)
    return fmt(shape_portfolio(balances, items(positions_resp)))


@guarded_tool
async def get_portfolio_history(account_number: str = "", time_back: str = "1m") -> str:
    """Get net-liq history summarized to start/end/change/drawdown plus a thinned series.

    Args:
        account_number: Account number; empty uses the default account.
        time_back: "1d", "1w", "1m", "3m", "6m", "1y", or "all".
    """
    client = get_client()
    acct = await resolve_account(account_number)
    resp = await client.get(f"/accounts/{acct}/net-liq/history", params={"time-back": time_back})
    return fmt(shape_history(items(resp)))


def register(mcp: FastMCP) -> None:
    mcp.tool()(list_accounts)
    mcp.tool()(get_portfolio)
    mcp.tool()(get_portfolio_history)
