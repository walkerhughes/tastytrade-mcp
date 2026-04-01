"""Unit tests for TastyTrade MCP server tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server import (
    _build_order_body,
    _fmt,
    _get_client,
    _items,
    cancel_order,
    get_accounts,
    get_balances,
    get_dividend_history,
    get_earnings_history,
    get_equity,
    get_live_orders,
    get_market_metrics,
    get_net_liq_history,
    get_option_chain,
    get_option_expirations,
    get_order_history,
    get_positions,
    get_public_watchlist,
    get_quote_token,
    get_trading_status,
    get_transactions,
    get_watchlists,
    place_order,
    preview_order,
    replace_order,
    search_symbols,
)

# ── Helper tests ─────────────────────────────────────────────────


@pytest.mark.unit
def test_fmt_returns_indented_json():
    result = _fmt({"key": "value"})
    parsed = json.loads(result)
    assert parsed == {"key": "value"}
    assert "\n" in result  # indented


@pytest.mark.unit
def test_items_extracts_from_items_key():
    resp = {"data": {"items": [{"id": 1}, {"id": 2}]}}
    assert _items(resp) == [{"id": 1}, {"id": 2}]


@pytest.mark.unit
def test_items_extracts_list_data():
    resp = {"data": [{"id": 1}]}
    assert _items(resp) == [{"id": 1}]


@pytest.mark.unit
def test_items_wraps_single_object():
    resp = {"data": {"id": 1, "name": "test"}}
    assert _items(resp) == [{"id": 1, "name": "test"}]


@pytest.mark.unit
def test_items_fallback_no_data_key():
    resp = {"items": [{"id": 1}]}
    assert _items(resp) == [{"id": 1}]


@pytest.mark.unit
def test_build_order_body():
    legs = [
        {
            "action": "Buy to Open",
            "symbol": "AAPL",
            "instrument-type": "Equity",
            "quantity": 100,
        }
    ]
    body = _build_order_body("Limit", "Day", legs, 150.0, "Debit")
    assert body["order-type"] == "Limit"
    assert body["time-in-force"] == "Day"
    assert body["price"] == "150.0"
    assert body["price-effect"] == "Debit"
    assert len(body["legs"]) == 1
    assert body["legs"][0]["action"] == "Buy to Open"


@pytest.mark.unit
def test_build_order_body_no_price():
    legs = [
        {
            "action": "Buy",
            "symbol": "AAPL",
            "instrument-type": "Equity",
            "quantity": 10,
        }
    ]
    body = _build_order_body("Market", "Day", legs, None, "")
    assert "price" not in body
    assert "price-effect" not in body


# ── Tool tests ───────────────────────────────────────────────────

MOCK_ACCOUNTS = [
    {
        "account": {
            "account-number": "5WT00001",
            "account-type-name": "Individual",
            "nickname": "Main",
            "margin-or-cash": "Margin",
            "is-closed": False,
        }
    }
]


def _mock_client(**overrides):
    """Create a mock TastyTradeClient with common defaults."""
    mock = MagicMock()
    mock.get_accounts = AsyncMock(return_value=MOCK_ACCOUNTS)
    mock.get_default_account_number = AsyncMock(return_value="5WT00001")
    mock.get = AsyncMock(return_value={"data": {}})
    mock.post = AsyncMock(return_value={"data": {}})
    mock.put = AsyncMock(return_value={"data": {}})
    mock.delete = AsyncMock(return_value={"data": {}})
    mock.customer_id = "U000123"
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_accounts_tool():
    mock = _mock_client()
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_accounts())
        assert len(result) == 1
        assert result[0]["account-number"] == "5WT00001"
        assert result[0]["account-type"] == "Individual"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balances_uses_default_account():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"net-liquidating-value": "50000.00"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_balances())
        assert result["net-liquidating-value"] == "50000.00"
        mock.get.assert_called_once_with("/accounts/5WT00001/balances")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balances_uses_provided_account():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"cash": "1000.00"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_balances(account_number="5WT99999"))
        assert result["cash"] == "1000.00"
        mock.get.assert_called_once_with("/accounts/5WT99999/balances")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_positions():
    positions = {
        "data": {
            "items": [
                {
                    "symbol": "AAPL",
                    "quantity": "100",
                    "quantity-direction": "Long",
                }
            ]
        }
    }
    mock = _mock_client(get=AsyncMock(return_value=positions))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_positions())
        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_transactions_with_filters():
    txns = {"data": {"items": [{"id": 1, "type": "Trade"}]}}
    mock = _mock_client(get=AsyncMock(return_value=txns))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_transactions(start_date="2025-01-01", symbol="AAPL"))
        assert len(result) == 1
        call_kwargs = mock.get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["start-date"] == "2025-01-01"
        assert params["symbol"] == "AAPL"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_live_orders():
    orders = {"data": {"items": [{"id": 123, "status": "Live"}]}}
    mock = _mock_client(get=AsyncMock(return_value=orders))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_live_orders())
        assert result[0]["status"] == "Live"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_preview_order():
    dry_run_resp = {
        "data": {
            "order": {"order-type": "Limit"},
            "warnings": [],
            "buying-power-effect": {"change-in-buying-power": "-15000.00"},
        }
    }
    mock = _mock_client(post=AsyncMock(return_value=dry_run_resp))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(
            await preview_order(
                order_type="Limit",
                time_in_force="Day",
                legs=[
                    {
                        "action": "Buy",
                        "symbol": "AAPL",
                        "instrument-type": "Equity",
                        "quantity": 100,
                    }
                ],
                price=150.0,
                price_effect="Debit",
            )
        )
        assert "buying-power-effect" in result
        call_args = mock.post.call_args
        assert "/orders/dry-run" in call_args[0][0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_order():
    mock = _mock_client(delete=AsyncMock(return_value={"data": {"id": 456, "status": "Cancelled"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await cancel_order(order_id="456"))
        assert result["status"] == "Cancelled"
        mock.delete.assert_called_once_with("/accounts/5WT00001/orders/456")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_symbols():
    symbols = {"data": {"items": [{"symbol": "AAPL", "description": "Apple Inc"}]}}
    mock = _mock_client(get=AsyncMock(return_value=symbols))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await search_symbols(query="AAPL"))
        assert result[0]["symbol"] == "AAPL"
        mock.get.assert_called_once_with("/symbols/search/AAPL")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_market_metrics():
    metrics = {
        "data": {
            "items": [
                {
                    "symbol": "AAPL",
                    "implied-volatility-index": "0.25",
                    "implied-volatility-rank": "45.2",
                }
            ]
        }
    }
    mock = _mock_client(get=AsyncMock(return_value=metrics))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_market_metrics(symbols="AAPL,SPY"))
        assert result[0]["symbol"] == "AAPL"
        mock.get.assert_called_once_with("/market-metrics", params={"symbols": "AAPL,SPY"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_trading_status():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"options-level": "Advanced"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_trading_status())
        assert result["options-level"] == "Advanced"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_net_liq_history():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"items": [{"close": "50000"}]}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_net_liq_history(time_back="3m"))
        assert result[0]["close"] == "50000"
        mock.get.assert_called_once_with(
            "/accounts/5WT00001/net-liq/history",
            params={"time-back": "3m"},
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_order_history():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"items": [{"id": 1, "status": "Filled"}]}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_order_history(status="Filled"))
        assert result[0]["status"] == "Filled"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_place_order():
    mock = _mock_client(post=AsyncMock(return_value={"data": {"order": {"id": 789}}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(
            await place_order(
                order_type="Market",
                time_in_force="Day",
                legs=[
                    {
                        "action": "Buy",
                        "symbol": "AAPL",
                        "instrument-type": "Equity",
                        "quantity": 10,
                    }
                ],
            )
        )
        assert result["order"]["id"] == 789
        call_args = mock.post.call_args
        assert call_args[0][0] == "/accounts/5WT00001/orders"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_replace_order():
    mock = _mock_client(put=AsyncMock(return_value={"data": {"id": 123, "status": "Live"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(
            await replace_order(
                order_id="123",
                order_type="Limit",
                time_in_force="Day",
                legs=[
                    {
                        "action": "Buy",
                        "symbol": "AAPL",
                        "instrument-type": "Equity",
                        "quantity": 10,
                    }
                ],
                price=155.0,
            )
        )
        assert result["id"] == 123


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_equity():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"symbol": "AAPL", "description": "Apple Inc"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_equity(symbol="AAPL"))
        assert result["symbol"] == "AAPL"


# ── Option chain tests ──────────────────────────────────────────

NESTED_CHAIN = {
    "data": {
        "items": [
            {
                "underlying-symbol": "SPY",
                "expirations": [
                    {
                        "expiration-date": "2026-04-17",
                        "days-to-expiration": 17,
                        "expiration-type": "Regular",
                        "settlement-type": "PM",
                        "strikes": [
                            {"strike-price": "195.0", "call": "SPY C", "put": "SPY P"},
                            {"strike-price": "200.0", "call": "SPY C", "put": "SPY P"},
                            {"strike-price": "205.0", "call": "SPY C", "put": "SPY P"},
                            {"strike-price": "210.0", "call": "SPY C", "put": "SPY P"},
                            {"strike-price": "215.0", "call": "SPY C", "put": "SPY P"},
                        ],
                    },
                    {
                        "expiration-date": "2026-05-15",
                        "days-to-expiration": 45,
                        "expiration-type": "Regular",
                        "settlement-type": "PM",
                        "strikes": [
                            {"strike-price": "200.0", "call": "SPY C", "put": "SPY P"},
                            {"strike-price": "210.0", "call": "SPY C", "put": "SPY P"},
                        ],
                    },
                ],
            }
        ]
    }
}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_option_expirations():
    mock = _mock_client(get=AsyncMock(return_value=NESTED_CHAIN))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_option_expirations(symbol="SPY"))
        assert len(result) == 2
        assert result[0]["expiration-date"] == "2026-04-17"
        assert result[0]["strikes-count"] == 5
        assert result[1]["days-to-expiration"] == 45


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_option_chain_filtered_by_expiration():
    mock = _mock_client(get=AsyncMock(return_value=NESTED_CHAIN))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_option_chain(symbol="SPY", expiration="2026-04-17"))
        assert len(result) == 1
        assert result[0]["expiration-date"] == "2026-04-17"
        assert len(result[0]["strikes"]) == 5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_option_chain_strikes_near():
    mock = _mock_client(get=AsyncMock(return_value=NESTED_CHAIN))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_option_chain(symbol="SPY", expiration="2026-04-17", strikes_near=1))
        # 5 strikes, mid=2 (index), +/-1 -> indices 1..3 -> 3 strikes
        assert len(result[0]["strikes"]) == 3
        assert result[0]["strikes"][1]["strike-price"] == "205.0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_option_chain_no_filter_returns_all():
    mock = _mock_client(get=AsyncMock(return_value=NESTED_CHAIN))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_option_chain(symbol="SPY"))
        assert len(result) == 2


# ── Remaining tool tests ────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_dividend_history():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"items": [{"amount": "0.24"}]}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_dividend_history(symbol="AAPL"))
        assert result[0]["amount"] == "0.24"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_earnings_history():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"items": [{"eps": "1.52"}]}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_earnings_history(symbol="AAPL", start_date="2024-01-01", end_date="2025-01-01"))
        assert result[0]["eps"] == "1.52"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_watchlists():
    mock = _mock_client()
    mock.get = AsyncMock(
        side_effect=[
            {"data": {"items": [{"name": "My List"}]}},
            {"data": {"items": [{"name": "TT Popular"}]}},
        ]
    )
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_watchlists())
        assert result["personal"][0]["name"] == "My List"
        assert result["public"][0]["name"] == "TT Popular"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_public_watchlist():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"name": "Popular", "entries": []}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_public_watchlist(name="Popular"))
        assert result["name"] == "Popular"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_quote_token():
    mock = _mock_client(get=AsyncMock(return_value={"data": {"token": "abc", "level": "delayed"}}))
    with patch("src.server._get_client", return_value=mock):
        result = json.loads(await get_quote_token())
        assert result["token"] == "abc"


@pytest.mark.unit
def test_get_client_lazy_init(monkeypatch):
    import src.server as mod

    monkeypatch.setenv("TT_CLIENT_ID", "test-id")
    monkeypatch.setenv("TT_SECRET", "test-secret")
    monkeypatch.setenv("TT_REFRESH", "test-refresh")
    monkeypatch.setenv("API_BASE_URL", "api.test.com")
    old = mod._client
    mod._client = None
    try:
        c = _get_client()
        assert c is not None
        # Subsequent calls return same instance
        assert _get_client() is c
    finally:
        mod._client = old
