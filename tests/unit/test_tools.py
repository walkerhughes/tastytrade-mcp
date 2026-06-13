"""Unit tests for v2 consolidated tools (mocked client)."""

import json

import pytest

from src.tools.accounts import get_portfolio, get_portfolio_history, list_accounts
from src.tools.market_data import get_market_data, search_symbols
from src.tools.options import get_option_chain
from src.tools.orders import cancel_order, list_orders, place_order, preview_order
from src.tools.transactions import query_transactions
from src.tools.watchlists import get_watchlists
from tests.unit.conftest import FakeClient

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


# accounts / portfolio


async def test_list_accounts_merges_trading_status(install_client):
    install_client(
        FakeClient(
            {
                "/customers/me/accounts": {
                    "data": {"items": [{"account": {"account-number": "5WT00001", "account-type-name": "Margin"}}]}
                },
                "trading-status": {"data": {"options-level": "Advanced", "day-trade-count": 1}},
            }
        )
    )
    out = json.loads(await list_accounts())
    assert out[0]["account_number"] == "5WT00001"
    assert out[0]["options_level"] == "Advanced"


async def test_get_portfolio_rolls_up_pnl(install_client):
    install_client(
        FakeClient(
            {
                "/balances": {"data": {"net-liquidating-value": "50000"}},
                "/positions": {
                    "data": {
                        "items": [
                            {
                                "symbol": "AAPL",
                                "underlying-symbol": "AAPL",
                                "quantity": "100",
                                "quantity-direction": "Long",
                                "average-open-price": "150",
                                "mark-price": "155",
                                "multiplier": "1",
                                "instrument-type": "Equity",
                            }
                        ]
                    }
                },
            }
        )
    )
    out = json.loads(await get_portfolio())
    assert out["summary"]["position_count"] == 1
    assert out["summary"]["total_unrealized_pnl"] == 500.0  # (155-150)*100
    assert out["positions"][0]["value"] == 15500.0


async def test_get_portfolio_history_summary(install_client):
    snaps = [{"time": f"2026-0{i}-01", "close": str(v)} for i, v in enumerate([100, 120, 90, 110], start=1)]
    install_client(FakeClient({"/net-liq/history": {"data": {"items": snaps}}}))
    out = json.loads(await get_portfolio_history())
    assert out["summary"]["start_value"] == 100
    assert out["summary"]["end_value"] == 110
    assert out["summary"]["high"] == 120
    assert out["summary"]["max_drawdown_pct"] == 25.0  # 120 -> 90


# market data


async def test_search_symbols_shaped(install_client):
    install_client(
        FakeClient({"/symbols/search": {"data": {"items": [{"symbol": "AAPL", "description": "Apple", "x": 1}]}}})
    )
    out = json.loads(await search_symbols("AAPL"))
    assert out[0] == {"symbol": "AAPL", "description": "Apple", "instrument_type": None}


async def test_get_market_data_quote_and_metrics(install_client):
    install_client(
        FakeClient(
            {
                "/market-data/by-type": {
                    "data": {"items": [{"symbol": "AAPL", "bid": 210.0, "ask": 210.2, "last": 210.1, "close": 208.0}]}
                },
                "/market-metrics": {"data": {"items": [{"symbol": "AAPL", "implied-volatility-index-rank": "45.2"}]}},
            }
        )
    )
    out = json.loads(await get_market_data(["AAPL"], include=["quote", "metrics"]))
    assert out[0]["quote"]["mid"] == 210.1
    assert out[0]["quote"]["day_change"] == 2.1
    assert out[0]["metrics"]["iv_rank"] == 45.2


async def test_get_market_data_rejects_bad_facet(install_client):
    install_client(FakeClient())
    out = json.loads(await get_market_data(["AAPL"], include=["nonsense"]))
    assert "error" in out


# options

NESTED = {
    "data": {
        "items": [
            {
                "underlying-symbol": "SPY",
                "expirations": [
                    {
                        "expiration-date": "2026-04-17",
                        "days-to-expiration": 17,
                        "strikes": [
                            {"strike-price": "195.0", "call": "C195", "put": "P195"},
                            {"strike-price": "200.0", "call": "C200", "put": "P200"},
                            {"strike-price": "205.0", "call": "C205", "put": "P205"},
                        ],
                    }
                ],
            }
        ]
    }
}


async def test_option_chain_lists_expirations_when_no_date(install_client):
    install_client(FakeClient({"/option-chains/": NESTED}))
    out = json.loads(await get_option_chain("SPY"))
    assert out["mode"] == "expirations"
    assert out["expirations"][0]["expiration_date"] == "2026-04-17"


async def test_option_chain_returns_enriched_strikes(install_client):
    install_client(
        FakeClient(
            {
                "/option-chains/": NESTED,
                "/market-data/by-type": {
                    "data": {
                        "items": [
                            {
                                "symbol": "C200",
                                "bid": 2.0,
                                "ask": 2.2,
                                "mid": 2.1,
                                "volume": 500,
                                "open-interest": 1000,
                            },
                            {"symbol": "P200", "bid": 1.9, "ask": 2.1, "mid": 2.0, "volume": 300, "open-interest": 800},
                        ]
                    }
                },
            }
        )
    )
    out = json.loads(await get_option_chain("SPY", expiration="2026-04-17", strikes_near=0))
    assert out["mode"] == "strikes"
    assert out["summary"]["n_strikes"] == 3
    assert out["summary"]["atm_strike"] == 200.0  # call/put mids closest at 200
    assert any(t["symbol"] == "C200" for t in out["summary"]["top_volume"])


async def test_option_chain_unknown_expiration(install_client):
    install_client(FakeClient({"/option-chains/": NESTED}))
    out = json.loads(await get_option_chain("SPY", expiration="2099-01-01"))
    assert "error" in out


# transactions


async def test_query_transactions_summary_and_pagination(install_client):
    txns = [
        {
            "id": i,
            "transaction-type": "Trade",
            "net-value": "100",
            "net-value-effect": "Credit",
            "commission": "1",
            "executed-at": f"2026-01-0{i}",
        }
        for i in range(1, 6)
    ]
    install_client(FakeClient({"/transactions": {"data": {"items": txns, "pagination": {"total-pages": 1}}}}))
    out = json.loads(await query_transactions(limit=2))
    assert out["summary"]["count"] == 5
    assert out["summary"]["net_cash_effect"] == 500.0
    assert out["summary"]["total_fees"] == 5.0
    assert len(out["transactions"]) == 2
    assert out["pagination"]["total_pages"] == 3


async def test_query_transactions_rejects_bad_date(install_client):
    install_client(FakeClient())
    out = json.loads(await query_transactions(start_date="01-2026"))
    assert "error" in out


# orders


async def test_list_orders_live_shaped(install_client):
    install_client(
        FakeClient(
            {"/orders/live": {"data": {"items": [{"id": 1, "status": "Live", "order-type": "Limit", "legs": []}]}}}
        )
    )
    out = json.loads(await list_orders())
    assert out[0]["status"] == "Live"


async def test_preview_order_shapes_bp_and_fees(install_client):
    install_client(
        FakeClient(
            {
                "/dry-run": {
                    "data": {
                        "buying-power-effect": {
                            "change-in-buying-power": "-15000",
                            "change-in-buying-power-effect": "Debit",
                        },
                        "fee-calculation": {"total-fees": "1.50"},
                        "warnings": [{"message": "Low buying power"}],
                        "order": {"status": "Received"},
                    }
                }
            }
        )
    )
    order = {"order_type": "Limit", "price": 150, "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 100}]}
    out = json.loads(await preview_order(order))
    assert out["buying_power_change"] == -15000.0
    assert out["total_fees"] == 1.5
    assert out["warnings"] == ["Low buying power"]


async def test_place_order_blocked_when_trading_disabled(install_client, monkeypatch):
    monkeypatch.delenv("TT_ENABLE_TRADING", raising=False)
    install_client(FakeClient())
    order = {"order_type": "Market", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 1}]}
    out = json.loads(await place_order(order, confirm=True))
    assert "Trading is disabled" in out["error"]


async def test_place_order_requires_confirm(install_client, monkeypatch):
    monkeypatch.setenv("TT_ENABLE_TRADING", "true")
    install_client(FakeClient())
    order = {"order_type": "Market", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 1}]}
    out = json.loads(await place_order(order, confirm=False))
    assert "confirm=true is required" in out["error"]
    assert out["order"]["order-type"] == "Market"


async def test_place_order_submits_when_enabled_and_confirmed(install_client, monkeypatch):
    monkeypatch.setenv("TT_ENABLE_TRADING", "true")
    client = install_client(FakeClient({"/orders": {"data": {"order": {"id": 99, "status": "Received", "legs": []}}}}))
    order = {"order_type": "Market", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 1}]}
    out = json.loads(await place_order(order, confirm=True))
    assert out["placed"] is True
    assert any(b[0] == "POST" and b[1].endswith("/orders") for b in client.bodies)


async def test_place_order_replace_uses_put(install_client, monkeypatch):
    monkeypatch.setenv("TT_ENABLE_TRADING", "true")
    client = install_client(FakeClient({"/orders/": {"data": {"order": {"id": 7, "status": "Live", "legs": []}}}}))
    order = {"order_type": "Limit", "price": 1, "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 1}]}
    await place_order(order, confirm=True, replace_order_id="7")
    assert any(b[0] == "PUT" for b in client.bodies)


async def test_cancel_order(install_client):
    client = install_client(FakeClient({"/orders/": {"data": {"id": 5, "status": "Cancelled", "legs": []}}}))
    out = json.loads(await cancel_order("5"))
    assert out["cancelled"] is True
    assert any(c[0] == "DELETE" for c in client.calls)


# watchlists


async def test_get_watchlists_names_only(install_client):
    install_client(
        FakeClient(
            {
                "/watchlists": {"data": {"items": [{"name": "Mine"}]}},
                "/public-watchlists": {"data": {"items": [{"name": "Popular"}]}},
            }
        )
    )
    out = json.loads(await get_watchlists())
    assert out["personal"] == ["Mine"]
    assert out["public"] == ["Popular"]


async def test_get_watchlists_expands_named(install_client):
    install_client(
        FakeClient({"/watchlists/Mine": {"data": {"name": "Mine", "watchlist-entries": [{"symbol": "AAPL"}]}}})
    )
    out = json.loads(await get_watchlists(name="Mine"))
    assert out["symbols"] == ["AAPL"]
