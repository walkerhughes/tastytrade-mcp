"""Option chain tool — discovery (expirations) and filtered, quote-enriched strikes."""

from mcp.server.fastmcp import FastMCP

from ..infra.errors import guarded_tool
from ..schemas.chain import ChainQuery
from ..shaping.chain import collect_symbols, list_expirations, select_strikes, shape_chain
from .base import cached_fetch, fmt, get_client, items


@guarded_tool
async def get_option_chain(
    symbol: str,
    expiration: str = "",
    strikes_near: int = 10,
    dte_max: int | None = None,
    option_type: str = "",
    include_quotes: bool = True,
) -> str:
    """Explore an option chain. Two modes in one tool.

    Omit `expiration` to list available expirations (cheap discovery step). Pass an
    `expiration` (YYYY-MM-DD) to get strikes around the money, enriched with live quotes,
    plus a `summary` (ATM strike, IV range, top strikes by volume / open interest).

    Args:
        symbol: Underlying ticker, e.g. "SPY".
        expiration: Expiration date YYYY-MM-DD. Omit to list expirations first.
        strikes_near: Strikes above and below ATM to return (0 = all). Default 10.
        dte_max: When listing expirations, only those within this many days.
        option_type: "call", "put", or "" for both.
        include_quotes: Enrich strikes with live quotes (default true).
    """
    query = ChainQuery(
        symbol=symbol,
        expiration=expiration,
        strikes_near=strikes_near,
        dte_max=dte_max,
        option_type=option_type,  # type: ignore[arg-type]
        include_quotes=include_quotes,
    )
    client = get_client()
    chain = await cached_fetch(
        "option_chain", f"nested:{query.symbol}", lambda: client.get(f"/option-chains/{query.symbol}/nested")
    )
    chain_items = items(chain)

    if not query.expiration:
        expirations = list_expirations(chain_items, query.dte_max)
        return fmt(
            {
                "symbol": query.symbol,
                "mode": "expirations",
                "expirations": expirations,
                "hint": "Call again with an expiration to get strikes and quotes.",
            }
        )

    meta, strikes = select_strikes(chain_items, query.expiration, query.strikes_near)
    if meta is None:
        available = [e["expiration_date"] for e in list_expirations(chain_items)]
        return fmt(
            {
                "error": f"No expiration {query.expiration} for {query.symbol}.",
                "suggestions": [f"Available expirations: {available[:12]}"],
            }
        )

    quotes_by_symbol: dict[str, dict] = {}
    if query.include_quotes:
        occ_symbols = collect_symbols(strikes, query.option_type)
        if occ_symbols:
            # Batch quotes in chunks to respect API symbol limits.
            for chunk in _chunks(occ_symbols, 90):
                resp = await cached_fetch(
                    "quotes",
                    f"opt:{','.join(chunk)}",
                    lambda c=chunk: client.get("/market-data/by-type", params={"equity-option": ",".join(c)}),
                )
                for q in items(resp):
                    if q.get("symbol"):
                        quotes_by_symbol[q["symbol"]] = q

    result = shape_chain(meta, strikes, quotes_by_symbol, query.option_type)
    result["symbol"] = query.symbol
    result["mode"] = "strikes"
    return fmt(result)


def _chunks(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def register(mcp: FastMCP) -> None:
    mcp.tool()(get_option_chain)
