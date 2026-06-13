"""Unit tests for Pydantic schemas: auto-correction + semantic validation."""

import pytest
from pydantic import ValidationError

from src.schemas.chain import ChainQuery
from src.schemas.common import is_option_symbol, validate_date
from src.schemas.orders import OrderLeg, OrderRequest

# common


@pytest.mark.unit
def test_is_option_symbol():
    assert is_option_symbol("AAPL  260116C00150000")
    assert not is_option_symbol("AAPL")
    assert not is_option_symbol("SPY")


@pytest.mark.unit
def test_validate_date_rejects_bad_format():
    with pytest.raises(ValueError):
        validate_date("01/17/2026", "expiration")
    assert validate_date("2026-01-17") == "2026-01-17"


# OrderLeg auto-correction


@pytest.mark.unit
def test_order_leg_autocorrects_kebab_keys_and_enum_and_str_qty():
    leg = OrderLeg.model_validate(
        {"action": "buy_to_open", "symbol": "AAPL", "instrument-type": "equity", "quantity": "100"}
    )
    assert leg.action == "Buy to Open"
    assert leg.instrument_type == "Equity"
    assert leg.quantity == 100


@pytest.mark.unit
def test_order_leg_infers_instrument_type_from_symbol():
    equity = OrderLeg.model_validate({"action": "Buy", "symbol": "AAPL", "quantity": 1})
    assert equity.instrument_type == "Equity"
    opt = OrderLeg.model_validate({"action": "Buy to Open", "symbol": "AAPL  260116C00150000", "quantity": 1})
    assert opt.instrument_type == "Equity Option"


@pytest.mark.unit
def test_order_leg_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        OrderLeg.model_validate({"action": "Buy", "symbol": "AAPL", "quantity": 0})


# OrderRequest semantic validation


@pytest.mark.unit
def test_order_request_limit_requires_price():
    with pytest.raises(ValidationError) as exc:
        OrderRequest.model_validate(
            {"order_type": "Limit", "legs": [{"action": "Buy", "symbol": "AAPL", "quantity": 1}]}
        )
    assert "price is required" in str(exc.value)


@pytest.mark.unit
def test_order_request_market_ok_without_price_and_builds_body():
    order = OrderRequest.model_validate(
        {"order_type": "market", "legs": [{"action": "buy", "symbol": "AAPL", "quantity": 10}]}
    )
    body = order.to_api_body()
    assert body["order-type"] == "Market"
    assert body["legs"][0]["instrument-type"] == "Equity"
    assert "price" not in body


@pytest.mark.unit
def test_order_request_option_limit_requires_price_effect():
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(
            {
                "order_type": "Limit",
                "price": 1.50,
                "legs": [{"action": "Buy to Open", "symbol": "AAPL  260116C00150000", "quantity": 1}],
            }
        )


@pytest.mark.unit
def test_order_request_too_many_legs():
    legs = [{"action": "Buy", "symbol": "AAPL", "quantity": 1}] * 5
    with pytest.raises(ValidationError):
        OrderRequest.model_validate({"order_type": "Market", "legs": legs})


# ChainQuery


@pytest.mark.unit
def test_chain_query_aliases_and_defaults():
    q = ChainQuery.model_validate({"symbol": "SPY", "expiration_date": "2026-04-17", "type": "CALL"})
    assert q.expiration == "2026-04-17"
    assert q.option_type == "call"
    assert q.strikes_near == 10
    assert q.include_quotes is True


@pytest.mark.unit
def test_chain_query_rejects_bad_date():
    with pytest.raises(ValidationError):
        ChainQuery.model_validate({"symbol": "SPY", "expiration": "April 17"})
