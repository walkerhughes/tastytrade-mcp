"""MCP tool modules. Each exposes ``register(mcp)`` to attach its tools."""

from mcp.server.fastmcp import FastMCP

from .accounts import register as register_accounts
from .market_data import register as register_market_data
from .options import register as register_options
from .orders import register as register_orders
from .transactions import register as register_transactions
from .watchlists import register as register_watchlists


def register_all(mcp: FastMCP) -> None:
    """Register every tool group on the given FastMCP server."""
    register_accounts(mcp)
    register_market_data(mcp)
    register_options(mcp)
    register_transactions(mcp)
    register_orders(mcp)
    register_watchlists(mcp)
