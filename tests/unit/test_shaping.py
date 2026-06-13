"""Unit tests for shaping helpers and summary builders."""

import pytest

from src.shaping.chain import collect_symbols, list_expirations, select_strikes
from src.shaping.market_data import shape_quote
from src.shaping.portfolio import shape_position
from src.shaping.summarize import downsample, max_drawdown, stats, top_n
from src.shaping.transactions import shape_transaction, summarize_transactions

pytestmark = pytest.mark.unit


# ── summarize ────────────────────────────────────────────────────


def test_stats_ignores_non_numeric():
    s = stats(["1", "2", "abc", 3])
    assert s["min"] == 1 and s["max"] == 3 and s["count"] == 3


def test_top_n_orders_desc_with_labels():
    rows = [{"sym": "A", "v": 5}, {"sym": "B", "v": 50}, {"sym": "C", "v": 1}]
    out = top_n(rows, "v", n=2, label_keys=("sym",))
    assert [r["sym"] for r in out] == ["B", "A"]


def test_downsample_keeps_last():
    out = downsample(list(range(100)), 10)
    assert len(out) == 10
    assert out[-1] == 99


def test_max_drawdown():
    assert max_drawdown([100, 120, 90, 110]) == pytest.approx(0.25)


# ── positions ────────────────────────────────────────────────────


def test_shape_position_short_pnl():
    pos = {
        "symbol": "SPY",
        "quantity": "2",
        "quantity-direction": "Short",
        "average-open-price": "5.00",
        "mark-price": "4.00",
        "multiplier": "100",
        "instrument-type": "Equity Option",
    }
    out = shape_position(pos)
    # short: profit when price falls. (4-5)*2*100*(-1) = +200
    assert out["pnl"] == 200.0


# ── transactions ─────────────────────────────────────────────────


def test_summarize_transactions_signs_cash():
    raw = [
        {"transaction-type": "Trade", "net-value": "100", "net-value-effect": "Credit"},
        {"transaction-type": "Trade", "net-value": "40", "net-value-effect": "Debit"},
    ]
    rows = [shape_transaction(t) for t in raw]
    s = summarize_transactions(rows)
    assert s["net_cash_effect"] == 60.0
    assert s["by_type"]["Trade"] == 2


# ── market data ──────────────────────────────────────────────────


def test_shape_quote_computes_mid_from_bid_ask():
    out = shape_quote({"symbol": "X", "bid": 10.0, "ask": 11.0})
    assert out["mid"] == 10.5


# ── chain ────────────────────────────────────────────────────────

NESTED = [
    {
        "expirations": [
            {
                "expiration-date": "2026-04-17",
                "days-to-expiration": 17,
                "strikes": [{"strike-price": "200", "call": "C200", "put": "P200"}],
            },
            {
                "expiration-date": "2026-06-19",
                "days-to-expiration": 80,
                "strikes": [{"strike-price": "200", "call": "C200b", "put": "P200b"}],
            },
        ]
    }
]


def test_list_expirations_dte_filter():
    out = list_expirations(NESTED, dte_max=30)
    assert len(out) == 1
    assert out[0]["expiration_date"] == "2026-04-17"


def test_select_strikes_and_collect_symbols():
    meta, strikes = select_strikes(NESTED, "2026-04-17", strikes_near=0)
    assert meta["days_to_expiration"] == 17
    assert collect_symbols(strikes, "call") == ["C200"]
    assert collect_symbols(strikes, "") == ["C200", "P200"]
