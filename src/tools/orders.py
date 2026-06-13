"""Order tools: list, preview, place (gated), cancel. Replace folds into place."""

from mcp.server.fastmcp import FastMCP

from ..config import get_settings
from ..infra.errors import error_response, guarded_tool
from ..schemas.orders import OrderRequest
from ..shaping.orders import shape_order, shape_preview
from .base import fmt, get_client, items, resolve_account


@guarded_tool
async def list_orders(
    account_number: str = "",
    scope: str = "live",
    status: str = "",
    start_date: str = "",
    end_date: str = "",
    underlying_symbol: str = "",
) -> str:
    """List orders. `scope="live"` for today's working orders, `scope="history"` for past.

    Args:
        account_number: Account number; empty uses the default account.
        scope: "live" or "history".
        status: History filter, e.g. "Filled", "Cancelled".
        start_date: History start date YYYY-MM-DD.
        end_date: History end date YYYY-MM-DD.
        underlying_symbol: Filter by underlying symbol.
    """
    client = get_client()
    acct = await resolve_account(account_number)
    if scope == "live":
        resp = await client.get(f"/accounts/{acct}/orders/live")
    else:
        params: dict[str, object] = {"per-page": 100, "account-numbers[]": acct}
        if start_date:
            params["start-date"] = start_date
        if end_date:
            params["end-date"] = end_date
        if underlying_symbol:
            params["underlying-symbol"] = underlying_symbol
        if status:
            params["status[]"] = status
        resp = await client.get(f"/customers/{client.customer_id}/orders", params=params)
    return fmt([shape_order(o) for o in items(resp)])


@guarded_tool
async def preview_order(order: dict, account_number: str = "") -> str:
    """Dry-run an order to see fees, buying-power impact, and warnings WITHOUT placing it.

    Always preview before placing. The `order` object:
      {"order_type": "Limit"|"Market"|"Stop"|"Stop Limit",
       "time_in_force": "Day"|"GTC"|...,
       "price": <number, required for Limit/Stop Limit>,
       "price_effect": "Debit"|"Credit"  (required for options/multi-leg),
       "legs": [{"action": "Buy"|"Sell"|"Buy to Open"|..., "symbol": "AAPL",
                 "quantity": <int>, "instrument_type": "Equity"|"Equity Option" (optional)}]}

    Args:
        order: The order specification (see above).
        account_number: Account number; empty uses the default account.
    """
    req = OrderRequest.model_validate(order)
    client = get_client()
    acct = await resolve_account(account_number)
    resp = await client.post(f"/accounts/{acct}/orders/dry-run", json=req.to_api_body())
    return fmt(shape_preview(resp.get("data", resp)))


@guarded_tool
async def place_order(
    order: dict,
    account_number: str = "",
    confirm: bool = False,
    replace_order_id: str = "",
) -> str:
    """Place (or replace) a REAL order. Executes a live trade.

    Two safety gates must both pass:
      1. The server must be started with TT_ENABLE_TRADING=true.
      2. You must pass confirm=true on this call.
    If either is missing the order is NOT sent and guidance is returned. Use preview_order
    first. `order` has the same shape as preview_order. Pass `replace_order_id` to modify an
    existing working order instead of creating a new one.

    Args:
        order: The order specification (see preview_order).
        account_number: Account number; empty uses the default account.
        confirm: Must be true to actually transmit the order.
        replace_order_id: If set, replace this existing order instead of creating one.
    """
    req = OrderRequest.model_validate(order)
    settings = get_settings()
    if not settings.enable_trading:
        return error_response(
            "Trading is disabled on this server, so the order was NOT placed.",
            [
                "Set TT_ENABLE_TRADING=true in the server environment to allow live orders.",
                "You can still use preview_order to inspect fees and buying-power impact.",
            ],
        )
    if not confirm:
        return error_response(
            "Order NOT placed: confirm=true is required to transmit a live order.",
            ["Re-call place_order with confirm=true once you have verified the preview."],
            order=req.to_api_body(),
        )

    client = get_client()
    acct = await resolve_account(account_number)
    if replace_order_id:
        resp = await client.put(f"/accounts/{acct}/orders/{replace_order_id}", json=req.to_api_body())
    else:
        resp = await client.post(f"/accounts/{acct}/orders", json=req.to_api_body())
    data = resp.get("data", resp)
    order_obj = data.get("order", data) if isinstance(data, dict) else data
    return fmt({"placed": True, "order": shape_order(order_obj) if isinstance(order_obj, dict) else order_obj})


@guarded_tool
async def cancel_order(order_id: str, account_number: str = "") -> str:
    """Cancel a live/working order.

    Args:
        order_id: Order id to cancel (from list_orders).
        account_number: Account number; empty uses the default account.
    """
    client = get_client()
    acct = await resolve_account(account_number)
    resp = await client.delete(f"/accounts/{acct}/orders/{order_id}")
    data = resp.get("data", resp)
    return fmt({"cancelled": True, "order": shape_order(data) if isinstance(data, dict) and data else data})


def register(mcp: FastMCP) -> None:
    mcp.tool()(list_orders)
    mcp.tool()(preview_order)
    mcp.tool()(place_order)
    mcp.tool()(cancel_order)
