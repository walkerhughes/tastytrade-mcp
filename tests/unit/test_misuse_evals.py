"""Deterministic checks that realistic model mistakes get corrected or guided.

These check the behavior at the tool boundary. A predictable mistake is corrected when that
is safe, and otherwise the tool returns an error with suggestions rather than a traceback or
a quietly wrong result. They run in CI through `make check`.
"""

import json

import pytest

from src.tools.market_data import get_market_data
from src.tools.orders import preview_order
from tests.unit.conftest import FakeClient

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

DRY_RUN_OK = {
    "/dry-run": {
        "data": {
            "buying-power-effect": {"change-in-buying-power": "-100", "change-in-buying-power-effect": "Debit"},
            "fee-calculation": {"total-fees": "1.00"},
            "warnings": [],
            "order": {"status": "Received"},
        }
    }
}


async def test_lowercase_and_kebab_order_is_autocorrected(install_client):
    """Lowercase enums, kebab keys, and a string quantity should all just work."""
    install_client(FakeClient(DRY_RUN_OK))
    order = {
        "order-type": "limit",  # kebab key + lowercase value
        "time-in-force": "day",
        "price": 1.50,
        "price-effect": "debit",
        "legs": [{"action": "buy_to_open", "symbol": "AAPL  260116C00150000", "quantity": "1"}],
    }
    out = json.loads(await preview_order(order))
    assert "error" not in out
    assert out["total_fees"] == 1.0


async def test_limit_without_price_returns_guided_error(install_client):
    install_client(FakeClient(DRY_RUN_OK))
    order = {"order_type": "Limit", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 1}]}
    out = json.loads(await preview_order(order))
    assert "error" in out
    assert any("price is required" in s for s in out["suggestions"])


async def test_zero_quantity_rejected_with_guidance(install_client):
    install_client(FakeClient(DRY_RUN_OK))
    order = {"order_type": "Market", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 0}]}
    out = json.loads(await preview_order(order))
    assert "error" in out and out["suggestions"]


async def test_bad_facet_lists_valid_options(install_client):
    install_client(FakeClient())
    out = json.loads(await get_market_data(["AAPL"], include=["quotes"]))  # should be "quote"
    assert "error" in out
    assert any("quote" in s for s in out["suggestions"])


async def test_unknown_symbol_404_is_guided(install_client):
    import httpx

    def raise_404():
        req = httpx.Request("GET", "https://x/market-data/by-type")
        raise httpx.HTTPStatusError("nf", request=req, response=httpx.Response(404, request=req))

    install_client(FakeClient({"/market-data/by-type": raise_404}))
    out = json.loads(await get_market_data(["ZZZZ"], include=["quote"]))
    assert out["status_code"] == 404
    assert any("search_symbols" in s for s in out["suggestions"])
