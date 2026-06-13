"""Tastytrade MCP server (v2).

Curated, task-oriented tools for an LLM rather than 1:1 REST wrappers. See
docs/design/2026-06-mcp-v2.md for the design rationale.

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
    """Construct and configure the FastMCP server with all v2 tools."""
    configure_logging(get_settings().log_level)
    mcp = FastMCP("tastytrade", instructions=INSTRUCTIONS)
    register_all(mcp)
    return mcp


mcp = build_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
