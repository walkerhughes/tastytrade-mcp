"""End-to-end tool tests against the in-process mock Tastytrade API.

These run the real client (auth, retry, envelope handling) together with the tool shaping
and check the exact values the fixtures encode, the same ground truth the Harbor benchmark
verifiers use.
"""

import json

import pytest

from src.tools.accounts import get_portfolio, get_portfolio_history, list_accounts
from src.tools.market_data import get_market_data, search_symbols
from src.tools.options import get_option_chain
from src.tools.orders import cancel_order, list_orders, place_order, preview_order
from src.tools.transactions import query_transactions
from src.tools.watchlists import get_watchlists
from tests.fixtures.mock_api.app import PLACED_ORDERS

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_list_accounts(tt_client):
    out = json.loads(await list_accounts())
    assert out[0]["account_number"] == "5WT00001"
    assert out[0]["options_level"] == "Advanced"


async def test_get_portfolio_total_pnl(tt_client):
    out = json.loads(await get_portfolio())
    # AAPL +500, SPY 200C +200 -> +700
    assert out["summary"]["total_unrealized_pnl"] == 700.0
    assert out["summary"]["net_liquidating_value"] == 52000.0
    assert out["summary"]["position_count"] == 2


async def test_get_portfolio_history_drawdown(tt_client):
    out = json.loads(await get_portfolio_history())
    # peak 53000 -> trough 47000 = ~11.32%
    assert out["summary"]["max_drawdown_pct"] == pytest.approx(11.32, abs=0.01)
    assert out["summary"]["end_value"] == 52000.0


async def test_search_and_market_data(tt_client):
    assert json.loads(await search_symbols("AAPL"))[0]["symbol"] == "AAPL"
    md = json.loads(await get_market_data(["AAPL"], include=["quote", "metrics", "dividends", "earnings"]))
    row = md[0]
    assert row["quote"]["mid"] == 210.5
    assert row["metrics"]["iv_rank"] == 42.5
    assert row["latest_dividend"]["amount"] == 0.24
    assert row["next_earnings"]["eps"] == "1.52"


async def test_option_chain_expirations_then_strikes(tt_client):
    listing = json.loads(await get_option_chain("SPY"))
    assert listing["mode"] == "expirations"
    dates = [e["expiration_date"] for e in listing["expirations"]]
    assert "2026-04-17" in dates

    chain = json.loads(await get_option_chain("SPY", expiration="2026-04-17", strikes_near=0))
    assert chain["summary"]["atm_strike"] == 200.0
    assert chain["summary"]["n_strikes"] == 3
    # 200 call has the most volume (900) in the fixture
    assert chain["summary"]["top_volume"][0]["strike"] == 200.0


async def test_query_transactions_summary(tt_client):
    out = json.loads(await query_transactions())
    # +15500 -15000 +24 = 524 net cash
    assert out["summary"]["net_cash_effect"] == 524.0
    assert out["summary"]["count"] == 3
    assert out["summary"]["by_type"]["Trade"] == 2


async def test_list_orders_live_and_history(tt_client):
    live = json.loads(await list_orders(scope="live"))
    assert live[0]["status"] == "Live"
    hist = json.loads(await list_orders(scope="history"))
    assert hist[0]["status"] == "Filled"


async def test_preview_order(tt_client):
    order = {"order_type": "Limit", "price": 150, "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 100}]}
    out = json.loads(await preview_order(order))
    assert out["buying_power_change"] == 15000.0
    assert out["total_fees"] == 1.16


async def test_place_order_records_body_when_enabled(tt_client, monkeypatch):
    monkeypatch.setenv("TT_ENABLE_TRADING", "true")
    order = {"order_type": "Market", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 5}]}
    out = json.loads(await place_order(order, confirm=True))
    assert out["placed"] is True
    assert PLACED_ORDERS[-1]["legs"][0]["quantity"] == 5
    assert PLACED_ORDERS[-1]["order-type"] == "Market"


async def test_place_order_blocked_without_gate(tt_client, monkeypatch):
    monkeypatch.delenv("TT_ENABLE_TRADING", raising=False)
    order = {"order_type": "Market", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 5}]}
    out = json.loads(await place_order(order, confirm=True))
    assert "Trading is disabled" in out["error"]


async def test_cancel_order(tt_client):
    out = json.loads(await cancel_order("555"))
    assert out["cancelled"] is True


async def test_get_watchlists(tt_client):
    names = json.loads(await get_watchlists())
    assert "My Tech" in names["personal"]
    detail = json.loads(await get_watchlists(name="My Tech"))
    assert detail["symbols"] == ["AAPL", "MSFT"]
