"""Tastytrade MCP server.

Task-oriented tools built for a model rather than one wrapper per REST endpoint. See
docs/design/2026-06-server-redesign.md for the reasoning.

Tool surface:
  Accounts/portfolio: list_accounts, get_portfolio, get_portfolio_history
  Market data:        search_symbols, get_market_data, get_option_chain
  Activity:           query_transactions, list_orders
  Trading:            preview_order, place_order (gated), cancel_order
  Watchlists:         get_watchlists
"""

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .infra.logging import configure_logging
from .tools import register_all

INSTRUCTIONS = (
    "Tastytrade brokerage tools. Discover accounts with list_accounts, then use "
    "get_portfolio for balances/positions/P&L. For market data use get_market_data; "
    "for options use get_option_chain (omit expiration first to list expirations, then "
    "pass one to get quote-enriched strikes). Always preview_order before place_order. "
    "Placing live orders requires the server's TT_ENABLE_TRADING flag AND confirm=true."
)


def build_server() -> FastMCP:
    """Construct and configure the FastMCP server with all tools."""
    configure_logging(get_settings().log_level)
    mcp = FastMCP("tastytrade", instructions=INSTRUCTIONS)
    register_all(mcp)
    return mcp


mcp = build_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
