"""Watchlist tool: names-only listing or one watchlist's symbols."""

from mcp.server.fastmcp import FastMCP

from ..infra.errors import guarded_tool
from .base import cached_fetch, fmt, get_client, items


@guarded_tool
async def get_watchlists(name: str = "") -> str:
    """List watchlist names, or fetch one watchlist's symbols.

    Omit `name` to get the (token-cheap) list of personal and public watchlist names. Pass
    a `name` to get that watchlist's symbols (personal first, falling back to public).

    Args:
        name: Watchlist name to expand. Empty lists names only.
    """
    client = get_client()
    if not name:
        personal = await cached_fetch("watchlists", "personal", lambda: client.get("/watchlists"))
        public = await cached_fetch("watchlists", "public", lambda: client.get("/public-watchlists"))
        return fmt(
            {
                "personal": [w.get("name") for w in items(personal)],
                "public": [w.get("name") for w in items(public)],
            }
        )

    try:
        resp = await client.get(f"/watchlists/{name}")
    except Exception:
        resp = await client.get(f"/public-watchlists/{name}")
    data = resp.get("data", resp)
    entries = data.get("watchlist-entries") or data.get("entries") or []
    symbols = [e.get("symbol") for e in entries if isinstance(e, dict)]
    return fmt({"name": data.get("name", name), "symbols": symbols})


def register(mcp: FastMCP) -> None:
    mcp.tool()(get_watchlists)
