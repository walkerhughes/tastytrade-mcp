"""Unit tests for infra: cache, correction, errors."""

import json

import httpx
import pytest

from src.infra.cache import TTLCache, access_collection
from src.infra.correction import coerce_int, match_enum, normalize_key, normalize_keys
from src.infra.errors import error_response, guarded_tool

# TTLCache


@pytest.mark.unit
def test_ttl_cache_hit_and_expiry():
    t = {"now": 0.0}
    cache = TTLCache(clock=lambda: t["now"])
    cache.set("k", {"v": 1}, ttl=10)
    assert cache.get("k") == {"v": 1}
    t["now"] = 11
    assert cache.get("k") is None


@pytest.mark.unit
def test_ttl_cache_zero_ttl_does_not_store():
    cache = TTLCache()
    cache.set("k", 1, ttl=0)
    assert cache.get("k") is None


@pytest.mark.unit
def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_keys=2)
    cache.set("a", 1, ttl=100)
    cache.set("b", 2, ttl=100)
    cache.get("a")  # a is now most-recently-used
    cache.set("c", 3, ttl=100)  # evicts b (LRU)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


# access_collection

ROWS = [
    {"symbol": "AAPL", "qty": 100, "value": 30},
    {"symbol": "SPY", "qty": 2, "value": 900},
    {"symbol": "TSLA", "qty": 5, "value": 50},
]


@pytest.mark.unit
def test_access_collection_pagination():
    out = access_collection(ROWS, page=1, limit=2)
    assert len(out["items"]) == 2
    assert out["pagination"]["total_items"] == 3
    assert out["pagination"]["total_pages"] == 2
    assert out["pagination"]["has_next"] is True


@pytest.mark.unit
def test_access_collection_sort_numeric_desc():
    out = access_collection(ROWS, sort_by="value", sort_order="desc", limit=10)
    assert [r["symbol"] for r in out["items"]] == ["SPY", "TSLA", "AAPL"]


@pytest.mark.unit
def test_access_collection_search():
    out = access_collection(ROWS, search="spy", limit=10)
    assert len(out["items"]) == 1
    assert out["items"][0]["symbol"] == "SPY"


# correction


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [("order-type", "order_type"), ("orderType", "order_type"), ("order_type", "order_type"), ("Symbol", "symbol")],
)
def test_normalize_key(raw, expected):
    assert normalize_key(raw) == expected


@pytest.mark.unit
def test_normalize_keys_recursive():
    data = {"order-type": "Limit", "legs": [{"instrument-type": "Equity"}]}
    assert normalize_keys(data) == {"order_type": "Limit", "legs": [{"instrument_type": "Equity"}]}


@pytest.mark.unit
def test_coerce_int():
    assert coerce_int("100") == 100
    assert coerce_int("-5") == -5
    assert coerce_int(3.0) == 3
    assert coerce_int("abc") == "abc"


@pytest.mark.unit
def test_match_enum_case_and_spacing_insensitive():
    assert match_enum("buy_to_open", ["Buy to Open", "Sell to Close"]) == "Buy to Open"
    assert match_enum("LIMIT", ["Limit", "Market"]) == "Limit"
    assert match_enum("nonsense", ["Limit"]) == "nonsense"  # unchanged -> validator flags it


# errors


@pytest.mark.unit
def test_error_response_shape():
    out = json.loads(error_response("boom", ["do x"], status_code=404))
    assert out["error"] == "boom"
    assert out["suggestions"] == ["do x"]
    assert out["status_code"] == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guarded_tool_maps_http_404():
    @guarded_tool
    async def tool() -> str:
        req = httpx.Request("GET", "https://x/y")
        resp = httpx.Response(404, request=req)
        raise httpx.HTTPStatusError("nope", request=req, response=resp)

    out = json.loads(await tool())
    assert out["status_code"] == 404
    assert any("search_symbols" in s for s in out["suggestions"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guarded_tool_parses_422_body():
    @guarded_tool
    async def tool() -> str:
        req = httpx.Request("POST", "https://x/orders")
        body = {"error": {"message": "Buying power exceeded", "errors": [{"message": "insufficient funds"}]}}
        resp = httpx.Response(422, request=req, json=body)
        raise httpx.HTTPStatusError("unprocessable", request=req, response=resp)

    out = json.loads(await tool())
    assert "Buying power exceeded" in out["error"]
    assert "insufficient funds" in out["suggestions"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guarded_tool_passes_through_success():
    @guarded_tool
    async def tool() -> str:
        return "ok"

    assert await tool() == "ok"
