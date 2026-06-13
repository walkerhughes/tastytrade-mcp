"""Market data: symbol search and a flexible per-symbol snapshot tool."""

from datetime import date, timedelta

from mcp.server.fastmcp import FastMCP

from ..infra.errors import error_response, guarded_tool
from ..schemas.common import is_option_symbol
from ..shaping.market_data import shape_market_data
from .base import cached_fetch, fmt, get_client, items

VALID_FACETS = {"quote", "metrics", "dividends", "earnings", "instrument"}


@guarded_tool
async def search_symbols(query: str) -> str:
    """Search tradeable symbols (stocks, ETFs, indices) by ticker or name.

    Args:
        query: Search text, e.g. "AAPL", "Apple", "SPY".
    """
    client = get_client()
    resp = await cached_fetch("instruments", f"search:{query}", lambda: client.get(f"/symbols/search/{query}"))
    shaped = [
        {"symbol": s.get("symbol"), "description": s.get("description"), "instrument_type": s.get("instrument-type")}
        for s in items(resp)
    ]
    return fmt(shaped)


@guarded_tool
async def get_market_data(symbols: list[str], include: list[str] | None = None) -> str:
    """Get a compact market snapshot for one or more symbols.

    One call replaces separate quote / IV-metrics / dividend / earnings / instrument
    lookups. Equity and OCC option symbols are auto-classified.

    Args:
        symbols: Tickers and/or OCC option symbols, e.g. ["AAPL", "SPY"].
        include: Facets to fetch. Any of: "quote", "metrics", "dividends", "earnings",
            "instrument". Defaults to ["quote", "metrics"].
    """
    include = include or ["quote", "metrics"]
    bad = [f for f in include if f not in VALID_FACETS]
    if bad:
        return error_response(
            f"Unknown include facet(s): {bad}.",
            [f"Valid facets are: {sorted(VALID_FACETS)}."],
        )
    if not symbols:
        return error_response("No symbols provided.", ['Pass at least one symbol, e.g. ["AAPL"].'])

    client = get_client()
    quotes: dict[str, dict] = {}
    metrics: dict[str, dict] = {}

    if "quote" in include:
        equities = [s for s in symbols if not is_option_symbol(s)]
        options = [s for s in symbols if is_option_symbol(s)]
        params: dict[str, str] = {}
        if equities:
            params["equity"] = ",".join(equities)
        if options:
            params["equity-option"] = ",".join(options)
        resp = await cached_fetch(
            "quotes", f"q:{','.join(symbols)}", lambda: client.get("/market-data/by-type", params=params)
        )
        for q in items(resp):
            quotes[q.get("symbol")] = q

    if "metrics" in include:
        equities = [s for s in symbols if not is_option_symbol(s)]
        if equities:
            resp = await cached_fetch(
                "market_metrics",
                f"m:{','.join(equities)}",
                lambda: client.get("/market-metrics", params={"symbols": ",".join(equities)}),
            )
            for m in items(resp):
                metrics[m.get("symbol")] = m

    out = []
    for sym in symbols:
        dividends = earnings = instrument = None
        if "dividends" in include and not is_option_symbol(sym):
            dividends = items(
                await cached_fetch(
                    "market_metrics",
                    f"div:{sym}",
                    lambda s=sym: client.get(f"/market-metrics/historic-corporate-events/dividends/{s}"),
                )
            )
        if "earnings" in include and not is_option_symbol(sym):
            start = (date.today() - timedelta(days=365)).isoformat()
            earnings = items(
                await cached_fetch(
                    "market_metrics",
                    f"earn:{sym}",
                    lambda s=sym: client.get(
                        f"/market-metrics/historic-corporate-events/earnings-reports/{s}",
                        params={"start-date": start},
                    ),
                )
            )
        if "instrument" in include and not is_option_symbol(sym):
            resp = await cached_fetch(
                "instruments", f"eq:{sym}", lambda s=sym: client.get(f"/instruments/equities/{s}")
            )
            instrument = resp.get("data", resp)
        out.append(
            shape_market_data(
                sym,
                quotes.get(sym) if "quote" in include else None,
                metrics.get(sym) if "metrics" in include else None,
                dividends,
                earnings,
                instrument,
            )
        )
    return fmt(out)


def register(mcp: FastMCP) -> None:
    mcp.tool()(search_symbols)
    mcp.tool()(get_market_data)
