"""Transaction query tool: fetch-once + cached local pagination/search/sort + summary."""

from mcp.server.fastmcp import FastMCP

from ..infra.cache import access_collection
from ..infra.errors import guarded_tool
from ..schemas.common import validate_date
from ..shaping.transactions import shape_transaction, summarize_transactions
from .base import cached_fetch, fmt, get_client, items, resolve_account

_MAX_PAGES = 4
_PER_PAGE = 250


async def _fetch_all(client, acct: str, base_params: dict) -> list[dict]:
    """Aggregate transaction pages up to a cap so paging can then be served locally."""
    collected: list[dict] = []
    for offset in range(_MAX_PAGES):
        params = {**base_params, "per-page": _PER_PAGE, "page-offset": offset}
        resp = await client.get(f"/accounts/{acct}/transactions", params=params)
        page = items(resp)
        collected.extend(page)
        pagination = (resp.get("data", {}) or {}).get("pagination", {}) if isinstance(resp.get("data"), dict) else {}
        total_pages = pagination.get("total-pages")
        if not page or (total_pages is not None and offset + 1 >= total_pages):
            break
    return collected


@guarded_tool
async def query_transactions(
    account_number: str = "",
    start_date: str = "",
    end_date: str = "",
    symbol: str = "",
    underlying_symbol: str = "",
    types: list[str] | None = None,
    page: int = 1,
    limit: int = 25,
    sort_by: str = "executed_at",
    sort_order: str = "desc",
    search: str = "",
) -> str:
    """Query transaction history with server-side filtering and a cash/fee summary.

    The matching transactions are fetched once and cached, so paging, sorting, and
    searching are served locally without re-hitting the API. The `summary` (net cash,
    total fees, counts by type) covers the full filtered set, not just the current page.

    Args:
        account_number: Account number; empty uses the default account.
        start_date: Filter start date YYYY-MM-DD.
        end_date: Filter end date YYYY-MM-DD.
        symbol: Filter by exact symbol.
        underlying_symbol: Filter by underlying symbol.
        types: Filter by transaction types, e.g. ["Trade", "Money Movement"].
        page: 1-based page of the local result set.
        limit: Items per page (default 25).
        sort_by: Field to sort by (default "executed_at").
        sort_order: "asc" or "desc".
        search: Case-insensitive substring filter across fields.
    """
    validate_date(start_date, "start_date")
    validate_date(end_date, "end_date")
    client = get_client()
    acct = await resolve_account(account_number)

    base_params: dict[str, object] = {}
    if start_date:
        base_params["start-date"] = start_date
    if end_date:
        base_params["end-date"] = end_date
    if symbol:
        base_params["symbol"] = symbol
    if underlying_symbol:
        base_params["underlying-symbol"] = underlying_symbol
    if types:
        base_params["type"] = types[0] if len(types) == 1 else ",".join(types)

    cache_key = f"{acct}:{sorted(base_params.items())}"
    raw = await cached_fetch("transactions", cache_key, lambda: _all_wrapper(client, acct, base_params))
    rows = [shape_transaction(t) for t in raw["items"]]

    page_data = access_collection(rows, page=page, limit=limit, sort_by=sort_by, sort_order=sort_order, search=search)
    return fmt(
        {
            "summary": summarize_transactions(rows),
            "pagination": page_data["pagination"],
            "transactions": page_data["items"],
        }
    )


async def _all_wrapper(client, acct: str, base_params: dict) -> dict:
    """Wrap the aggregated list in a dict so it round-trips through the dict cache."""
    return {"items": await _fetch_all(client, acct, base_params)}


def register(mcp: FastMCP) -> None:
    mcp.tool()(query_transactions)
