"""A Starlette app that emulates the slice of the Tastytrade API the MCP server uses.

Backed by the deterministic fixtures in ``data.py``. Order submissions are recorded
(in memory and, if ``MOCK_STATE_FILE`` is set, appended to a JSONL file) so Harbor
verifiers can assert exactly what the agent placed.

Run standalone:  uvicorn tests.fixtures.mock_api.app:app --port 8080
Use in-process:  httpx.ASGITransport(app=build_app())
"""

import base64
import json
import os
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import data

# A JWT-shaped token whose payload carries {"sub": "me"} so the client extracts the
# customer id exactly as it would in production.
_PAYLOAD = base64.urlsafe_b64encode(json.dumps({"sub": data.CUSTOMER_ID}).encode()).decode().rstrip("=")
ACCESS_TOKEN = f"header.{_PAYLOAD}.signature"

# Orders submitted during this process lifetime (also exposed for in-process assertions).
PLACED_ORDERS: list[dict] = []


def _record_order(body: Any) -> None:
    PLACED_ORDERS.append(body)
    state_file = os.environ.get("MOCK_STATE_FILE")
    if state_file:
        with open(state_file, "a") as fh:
            fh.write(json.dumps(body) + "\n")


def _ok(payload: dict) -> JSONResponse:
    return JSONResponse(payload)


async def oauth_token(request: Request) -> JSONResponse:
    return _ok({"access_token": ACCESS_TOKEN, "expires_in": 900, "token_type": "Bearer"})


async def accounts(request: Request) -> JSONResponse:
    return _ok(data.ACCOUNTS)


async def balances(request: Request) -> JSONResponse:
    return _ok(data.BALANCES)


async def positions(request: Request) -> JSONResponse:
    return _ok(data.POSITIONS)


async def trading_status(request: Request) -> JSONResponse:
    return _ok(data.TRADING_STATUS)


async def net_liq_history(request: Request) -> JSONResponse:
    return _ok(data.NET_LIQ_HISTORY)


async def transactions(request: Request) -> JSONResponse:
    return _ok(data.TRANSACTIONS)


async def live_orders(request: Request) -> JSONResponse:
    return _ok(data.LIVE_ORDERS)


async def customer_orders(request: Request) -> JSONResponse:
    return _ok(data.ORDER_HISTORY)


async def dry_run(request: Request) -> JSONResponse:
    body = await request.json()
    legs = body.get("legs", [])
    qty = sum(int(leg.get("quantity", 0)) for leg in legs)
    price = float(body.get("price", 0) or 0)
    est = round(qty * price * (100 if any("Option" in (leg.get("instrument-type") or "") for leg in legs) else 1), 2)
    return _ok(
        {
            "data": {
                "order": {"status": "Received", **body},
                "buying-power-effect": {
                    "change-in-buying-power": str(est),
                    "change-in-buying-power-effect": "Debit",
                    "new-buying-power": str(round(40000.0 - est, 2)),
                },
                "fee-calculation": {"total-fees": data.DRY_RUN_TOTAL_FEES},
                "warnings": [],
            }
        }
    )


async def place(request: Request) -> JSONResponse:
    body = await request.json()
    _record_order(body)
    return _ok({"data": {"order": {"id": 9001, "status": "Received", **body}}})


async def replace(request: Request) -> JSONResponse:
    body = await request.json()
    _record_order(body)
    order_id = request.path_params["order_id"]
    return _ok({"data": {"order": {"id": order_id, "status": "Received", **body}}})


async def cancel(request: Request) -> JSONResponse:
    order_id = request.path_params["order_id"]
    return _ok({"data": {"id": order_id, "status": "Cancelled"}})


async def symbol_search(request: Request) -> JSONResponse:
    query = request.path_params["query"].upper()
    return _ok(data.SYMBOL_SEARCH.get(query, {"data": {"items": []}}))


async def equity(request: Request) -> JSONResponse:
    sym = request.path_params["symbol"].upper()
    return _ok(data.EQUITIES.get(sym, {"data": {}}))


async def market_metrics(request: Request) -> JSONResponse:
    symbols = request.query_params.get("symbols", "")
    items = [data.MARKET_METRICS[s] for s in symbols.split(",") if s in data.MARKET_METRICS]
    return _ok({"data": {"items": items}})


async def dividends(request: Request) -> JSONResponse:
    sym = request.path_params["symbol"].upper()
    return _ok(data.DIVIDENDS.get(sym, {"data": {"items": []}}))


async def earnings(request: Request) -> JSONResponse:
    sym = request.path_params["symbol"].upper()
    return _ok(data.EARNINGS.get(sym, {"data": {"items": []}}))


async def option_chain(request: Request) -> JSONResponse:
    return _ok(data.OPTION_CHAIN)


async def market_data_by_type(request: Request) -> JSONResponse:
    requested: list[str] = []
    for param in ("equity", "equity-option", "index", "future"):
        val = request.query_params.get(param)
        if val:
            requested.extend(s for s in val.split(",") if s)
    items = [data.QUOTES[s] for s in requested if s in data.QUOTES]
    return _ok({"data": {"items": items}})


async def watchlists(request: Request) -> JSONResponse:
    return _ok(data.WATCHLISTS)


async def public_watchlists(request: Request) -> JSONResponse:
    return _ok(data.PUBLIC_WATCHLISTS)


async def watchlist_detail(request: Request) -> JSONResponse:
    name = request.path_params["name"]
    if name in data.WATCHLIST_DETAIL:
        return _ok(data.WATCHLIST_DETAIL[name])
    return JSONResponse({"error": {"code": "not_found", "message": "no such watchlist"}}, status_code=404)


async def public_watchlist_detail(request: Request) -> JSONResponse:
    name = request.path_params["name"]
    return _ok(data.PUBLIC_WATCHLIST_DETAIL.get(name, {"data": {}}))


def build_app() -> Starlette:
    """Construct a fresh app instance (clears the in-memory order log)."""
    PLACED_ORDERS.clear()
    routes = [
        Route("/oauth/token", oauth_token, methods=["POST"]),
        Route("/customers/me/accounts", accounts, methods=["GET"]),
        Route("/accounts/{account}/balances", balances, methods=["GET"]),
        Route("/accounts/{account}/positions", positions, methods=["GET"]),
        Route("/accounts/{account}/trading-status", trading_status, methods=["GET"]),
        Route("/accounts/{account}/net-liq/history", net_liq_history, methods=["GET"]),
        Route("/accounts/{account}/transactions", transactions, methods=["GET"]),
        Route("/accounts/{account}/orders/live", live_orders, methods=["GET"]),
        Route("/accounts/{account}/orders/dry-run", dry_run, methods=["POST"]),
        Route("/accounts/{account}/orders/{order_id}", replace, methods=["PUT"]),
        Route("/accounts/{account}/orders/{order_id}", cancel, methods=["DELETE"]),
        Route("/accounts/{account}/orders", place, methods=["POST"]),
        Route("/customers/{customer_id}/orders", customer_orders, methods=["GET"]),
        Route("/symbols/search/{query}", symbol_search, methods=["GET"]),
        Route("/instruments/equities/{symbol}", equity, methods=["GET"]),
        Route("/market-metrics", market_metrics, methods=["GET"]),
        Route("/market-metrics/historic-corporate-events/dividends/{symbol}", dividends, methods=["GET"]),
        Route("/market-metrics/historic-corporate-events/earnings-reports/{symbol}", earnings, methods=["GET"]),
        Route("/option-chains/{symbol}/nested", option_chain, methods=["GET"]),
        Route("/market-data/by-type", market_data_by_type, methods=["GET"]),
        Route("/watchlists", watchlists, methods=["GET"]),
        Route("/public-watchlists", public_watchlists, methods=["GET"]),
        Route("/watchlists/{name}", watchlist_detail, methods=["GET"]),
        Route("/public-watchlists/{name}", public_watchlist_detail, methods=["GET"]),
    ]
    return Starlette(routes=routes)


app = build_app()
