"""TastyTrade MCP server for Claude Code.

Exposes TastyTrade brokerage functionality as MCP tools:
  - Account info, balances, positions, transactions
  - Order management (preview, place, cancel)
  - Market data, option chains, volatility metrics
  - Watchlists
"""

import json

from mcp.server.fastmcp import FastMCP

from .client import TastyTradeClient

mcp = FastMCP(
    "tastytrade",
    instructions=(
        "TastyTrade brokerage tools. Use get_accounts to find account numbers, "
        "then query balances, positions, or place orders. Always use preview_order "
        "before place_order to verify fees and buying power impact."
    ),
)
_client: TastyTradeClient | None = None


def _get_client() -> TastyTradeClient:
    """Lazy-init so env vars are only read at runtime, not import time."""
    global _client
    if _client is None:
        _client = TastyTradeClient()
    return _client


# ── Helpers ──────────────────────────────────────────────────────


def _fmt(data: object) -> str:
    """Format response data as indented JSON."""
    return json.dumps(data, indent=2, default=str)


def _items(resp: dict) -> list:
    """Extract items from the standard TT response envelope."""
    data = resp.get("data", resp)
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    return [data]


def _build_order_body(
    order_type: str,
    time_in_force: str,
    legs: list[dict],
    price: float | None,
    price_effect: str,
) -> dict:
    """Build an order JSON body from tool parameters."""
    order: dict = {
        "order-type": order_type,
        "time-in-force": time_in_force,
        "legs": [
            {
                "action": leg["action"],
                "symbol": leg["symbol"],
                "instrument-type": leg["instrument-type"],
                "quantity": leg["quantity"],
            }
            for leg in legs
        ],
    }
    if price is not None:
        order["price"] = str(price)
    if price_effect:
        order["price-effect"] = price_effect
    return order


async def _resolve_account(account_number: str) -> str:
    """Use provided account number or fall back to default."""
    if account_number:
        return account_number
    return await _get_client().get_default_account_number()


# ── Account & Portfolio ──────────────────────────────────────────


@mcp.tool()
async def get_accounts() -> str:
    """List all TastyTrade trading accounts with numbers, types, and nicknames."""
    accounts = await _get_client().get_accounts()
    results = []
    for item in accounts:
        acct = item.get("account", item)
        results.append(
            {
                "account-number": acct.get("account-number"),
                "account-type": acct.get("account-type-name", acct.get("account-type")),
                "nickname": acct.get("nickname", ""),
                "margin-or-cash": acct.get("margin-or-cash"),
                "is-closed": acct.get("is-closed", False),
            }
        )
    return _fmt(results)


@mcp.tool()
async def get_balances(account_number: str = "") -> str:
    """Get account balances: net liquidating value, cash, buying power, and P&L.

    Args:
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    resp = await _get_client().get(f"/accounts/{acct}/balances")
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def get_positions(
    account_number: str = "",
    include_marks: bool = True,
    include_closed: bool = False,
) -> str:
    """Get current portfolio positions with quantities, cost basis, and market values.

    Args:
        account_number: Trading account number. Leave empty for default account.
        include_marks: Include current market prices for each position.
        include_closed: Include positions that have been fully closed.
    """
    acct = await _resolve_account(account_number)
    params = {
        "include-marks": str(include_marks).lower(),
        "include-closed-positions": str(include_closed).lower(),
    }
    resp = await _get_client().get(f"/accounts/{acct}/positions", params=params)
    return _fmt(_items(resp))


@mcp.tool()
async def get_trading_status(account_number: str = "") -> str:
    """Get account trading status: options level, margin type, day-trade status, and restrictions.

    Args:
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    resp = await _get_client().get(f"/accounts/{acct}/trading-status")
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def get_transactions(
    account_number: str = "",
    start_date: str = "",
    end_date: str = "",
    symbol: str = "",
    underlying_symbol: str = "",
    transaction_type: str = "",
    per_page: int = 50,
) -> str:
    """Get account transaction history (trades, dividends, fees, transfers).

    Args:
        account_number: Trading account number. Leave empty for default account.
        start_date: Start date filter (YYYY-MM-DD).
        end_date: End date filter (YYYY-MM-DD).
        symbol: Filter by exact symbol.
        underlying_symbol: Filter by underlying symbol.
        transaction_type: Filter by type (e.g. "Trade", "Receive Deliver").
        per_page: Results per page (1-2000, default 50).
    """
    acct = await _resolve_account(account_number)
    params: dict = {"per-page": per_page}
    if start_date:
        params["start-date"] = start_date
    if end_date:
        params["end-date"] = end_date
    if symbol:
        params["symbol"] = symbol
    if underlying_symbol:
        params["underlying-symbol"] = underlying_symbol
    if transaction_type:
        params["type"] = transaction_type
    resp = await _get_client().get(f"/accounts/{acct}/transactions", params=params)
    return _fmt(_items(resp))


@mcp.tool()
async def get_net_liq_history(
    account_number: str = "",
    time_back: str = "1m",
) -> str:
    """Get net liquidating value history for portfolio performance analysis.

    Args:
        account_number: Trading account number. Leave empty for default account.
        time_back: How far back: "1d", "1w", "1m", "3m", "6m", "1y", or "all".
    """
    acct = await _resolve_account(account_number)
    resp = await _get_client().get(f"/accounts/{acct}/net-liq/history", params={"time-back": time_back})
    return _fmt(_items(resp))


# ── Orders ───────────────────────────────────────────────────────


@mcp.tool()
async def get_live_orders(account_number: str = "") -> str:
    """Get all currently working/live orders for today's session.

    Args:
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    resp = await _get_client().get(f"/accounts/{acct}/orders/live")
    return _fmt(_items(resp))


@mcp.tool()
async def get_order_history(
    account_number: str = "",
    start_date: str = "",
    end_date: str = "",
    underlying_symbol: str = "",
    status: str = "",
    per_page: int = 50,
) -> str:
    """Get historical orders with optional filters.

    Args:
        account_number: Trading account number. Leave empty for default account.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        underlying_symbol: Filter by underlying symbol.
        status: Filter by status ("Filled", "Cancelled", "Expired", "Live", "Contingent").
        per_page: Results per page (default 50).
    """
    acct = await _resolve_account(account_number)
    c = _get_client()
    params: dict = {"per-page": per_page, "account-numbers[]": acct}
    if start_date:
        params["start-date"] = start_date
    if end_date:
        params["end-date"] = end_date
    if underlying_symbol:
        params["underlying-symbol"] = underlying_symbol
    if status:
        params["status[]"] = status
    resp = await c.get(f"/customers/{c.customer_id}/orders", params=params)
    return _fmt(_items(resp))


@mcp.tool()
async def preview_order(
    order_type: str,
    time_in_force: str,
    legs: list[dict],
    price: float | None = None,
    price_effect: str = "",
    account_number: str = "",
) -> str:
    """Dry-run an order to see fees, buying power impact, and warnings WITHOUT placing it.

    Always call this before place_order to verify the trade details.

    Args:
        order_type: "Limit", "Market", "Stop", or "Stop Limit".
        time_in_force: "Day", "GTC", "Ext", "GTC Ext", or "IOC".
        legs: Order legs list. Each leg dict needs keys:
              action - "Buy to Open"/"Buy to Close"/"Sell to Open"/
                "Sell to Close" (options) or "Buy"/"Sell" (equities)
              symbol - e.g. "AAPL" or OCC option symbol
              instrument-type - "Equity", "Equity Option", "Future",
                "Future Option", or "Cryptocurrency"
              quantity - Number of shares or contracts
        price: Limit price (required for Limit/Stop Limit orders).
        price_effect: "Debit" or "Credit" (required for options/multi-leg).
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    body = _build_order_body(order_type, time_in_force, legs, price, price_effect)
    resp = await _get_client().post(f"/accounts/{acct}/orders/dry-run", json=body)
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def place_order(
    order_type: str,
    time_in_force: str,
    legs: list[dict],
    price: float | None = None,
    price_effect: str = "",
    account_number: str = "",
) -> str:
    """Place a REAL order. Use preview_order first. THIS EXECUTES A LIVE TRADE.

    Args:
        order_type: "Limit", "Market", "Stop", or "Stop Limit".
        time_in_force: "Day", "GTC", "Ext", "GTC Ext", or "IOC".
        legs: Order legs list. Each leg dict needs keys:
              action - "Buy to Open"/"Buy to Close"/"Sell to Open"/
                "Sell to Close" (options) or "Buy"/"Sell" (equities)
              symbol - e.g. "AAPL" or OCC option symbol
              instrument-type - "Equity", "Equity Option", "Future",
                "Future Option", or "Cryptocurrency"
              quantity - Number of shares or contracts
        price: Limit price (required for Limit/Stop Limit orders).
        price_effect: "Debit" or "Credit" (required for options/multi-leg).
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    body = _build_order_body(order_type, time_in_force, legs, price, price_effect)
    resp = await _get_client().post(f"/accounts/{acct}/orders", json=body)
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def cancel_order(order_id: str, account_number: str = "") -> str:
    """Cancel a live/working order.

    Args:
        order_id: The order ID to cancel (get IDs from get_live_orders).
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    resp = await _get_client().delete(f"/accounts/{acct}/orders/{order_id}")
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def replace_order(
    order_id: str,
    order_type: str,
    time_in_force: str,
    legs: list[dict],
    price: float | None = None,
    price_effect: str = "",
    account_number: str = "",
) -> str:
    """Replace (modify) an existing live order with new parameters.

    Args:
        order_id: The order ID to replace (get IDs from get_live_orders).
        order_type: "Limit", "Market", "Stop", or "Stop Limit".
        time_in_force: "Day", "GTC", "Ext", "GTC Ext", or "IOC".
        legs: Order legs (same format as place_order).
        price: New limit price.
        price_effect: "Debit" or "Credit".
        account_number: Trading account number. Leave empty for default account.
    """
    acct = await _resolve_account(account_number)
    body = _build_order_body(order_type, time_in_force, legs, price, price_effect)
    resp = await _get_client().put(f"/accounts/{acct}/orders/{order_id}", json=body)
    return _fmt(resp.get("data", resp))


# ── Market Data & Instruments ────────────────────────────────────


@mcp.tool()
async def search_symbols(query: str) -> str:
    """Search for tradeable symbols (stocks, ETFs, indices) by name or ticker.

    Args:
        query: Search text (e.g. "AAPL", "Apple", "SPY").
    """
    resp = await _get_client().get(f"/symbols/search/{query}")
    return _fmt(_items(resp))


@mcp.tool()
async def get_equity(symbol: str) -> str:
    """Get detailed info about a stock or ETF: description, exchange, and trading status.

    Args:
        symbol: Ticker symbol (e.g. "AAPL", "SPY").
    """
    resp = await _get_client().get(f"/instruments/equities/{symbol}")
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def get_option_expirations(symbol: str) -> str:
    """List available option expiration dates for a symbol. Call this first,
    then use get_option_chain with a specific expiration to get strike details.

    Args:
        symbol: Underlying ticker symbol (e.g. "AAPL", "SPY").
    """
    resp = await _get_client().get(f"/option-chains/{symbol}/nested")
    data = resp.get("data", resp)
    items = data.get("items", [data]) if isinstance(data, dict) else data
    expirations = []
    for item in items:
        for exp in item.get("expirations", []):
            expirations.append(
                {
                    "expiration-date": exp["expiration-date"],
                    "days-to-expiration": exp["days-to-expiration"],
                    "expiration-type": exp.get("expiration-type"),
                    "settlement-type": exp.get("settlement-type"),
                    "strikes-count": len(exp.get("strikes", [])),
                }
            )
    return _fmt(expirations)


@mcp.tool()
async def get_option_chain(
    symbol: str,
    expiration: str = "",
    strikes_near: int = 0,
) -> str:
    """Get option chain strikes with call/put symbols for a symbol.

    Use get_option_expirations first to see available dates, then call this
    with a specific expiration to keep the response small.

    Args:
        symbol: Underlying ticker symbol (e.g. "AAPL", "SPY").
        expiration: Filter to a single expiration date (YYYY-MM-DD).
            Strongly recommended to avoid huge responses.
        strikes_near: If > 0, only return this many strikes above and
            below the at-the-money strike (e.g. 5 returns ~11 strikes).
    """
    resp = await _get_client().get(f"/option-chains/{symbol}/nested")
    data = resp.get("data", resp)
    items = data.get("items", [data]) if isinstance(data, dict) else data

    result = []
    for item in items:
        for exp in item.get("expirations", []):
            if expiration and exp["expiration-date"] != expiration:
                continue
            strikes = exp.get("strikes", [])
            if strikes_near > 0 and strikes:
                prices = [float(s["strike-price"]) for s in strikes]
                mid = len(prices) // 2
                lo = max(0, mid - strikes_near)
                hi = min(len(strikes), mid + strikes_near + 1)
                strikes = strikes[lo:hi]
            result.append(
                {
                    "expiration-date": exp["expiration-date"],
                    "days-to-expiration": exp["days-to-expiration"],
                    "strikes": strikes,
                }
            )
    return _fmt(result)


@mcp.tool()
async def get_market_metrics(symbols: str) -> str:
    """Get volatility and liquidity metrics: IV rank, IV percentile, liquidity rating.

    Args:
        symbols: Comma-separated symbols (e.g. "AAPL,SPY,TSLA").
    """
    resp = await _get_client().get("/market-metrics", params={"symbols": symbols})
    return _fmt(_items(resp))


@mcp.tool()
async def get_dividend_history(symbol: str) -> str:
    """Get historical dividend payments for a symbol.

    Args:
        symbol: Ticker symbol (e.g. "AAPL").
    """
    resp = await _get_client().get(f"/market-metrics/historic-corporate-events/dividends/{symbol}")
    return _fmt(_items(resp))


@mcp.tool()
async def get_earnings_history(symbol: str, start_date: str, end_date: str = "") -> str:
    """Get historical earnings report data (EPS and dates).

    Args:
        symbol: Ticker symbol (e.g. "AAPL").
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD, defaults to today).
    """
    params: dict = {"start-date": start_date}
    if end_date:
        params["end-date"] = end_date
    resp = await _get_client().get(
        f"/market-metrics/historic-corporate-events/earnings-reports/{symbol}",
        params=params,
    )
    return _fmt(_items(resp))


# ── Watchlists ───────────────────────────────────────────────────


@mcp.tool()
async def get_watchlists() -> str:
    """Get all personal and public TastyTrade watchlists."""
    c = _get_client()
    personal = await c.get("/watchlists")
    public = await c.get("/public-watchlists")
    return _fmt(
        {
            "personal": _items(personal),
            "public": _items(public),
        }
    )


@mcp.tool()
async def get_public_watchlist(name: str) -> str:
    """Get symbols in a specific public TastyTrade watchlist.

    Args:
        name: Watchlist name (get names from get_watchlists).
    """
    resp = await _get_client().get(f"/public-watchlists/{name}")
    return _fmt(resp.get("data", resp))


@mcp.tool()
async def get_quote_token() -> str:
    """Get a DXLink streaming quote token for real-time market data."""
    resp = await _get_client().get("/api-quote-tokens")
    return _fmt(resp.get("data", resp))


# ── Entry point ──────────────────────────────────────────────────


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
