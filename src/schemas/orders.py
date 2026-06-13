"""Schemas for an order, the write path that gets the most checking.

These follow the same idea as Honeycomb's query schema. Field descriptions are written for
the model and include correct and incorrect examples, ``mode="before"`` corrects the
arguments, and ``mode="after"`` checks them and raises with a clear message.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..infra.correction import coerce_int, match_enum, normalize_keys
from ..schemas.common import is_option_symbol

ACTIONS = ["Buy to Open", "Buy to Close", "Sell to Open", "Sell to Close", "Buy", "Sell"]
INSTRUMENT_TYPES = ["Equity", "Equity Option", "Future", "Future Option", "Cryptocurrency"]
ORDER_TYPES = ["Limit", "Market", "Stop", "Stop Limit"]
TIF = ["Day", "GTC", "Ext", "GTC Ext", "IOC"]
PRICE_EFFECTS = ["Debit", "Credit", ""]


class OrderLeg(BaseModel):
    """One leg of an order. Up to 4 legs make a multi-leg (e.g. a vertical spread)."""

    action: str = Field(description="One of: " + ", ".join(ACTIONS) + ". Equities use Buy/Sell.")
    symbol: str = Field(description="Equity ticker (AAPL) or OCC option symbol.")
    instrument_type: str = Field(default="", description="Equity, Equity Option, etc. Inferred if omitted.")
    quantity: int = Field(gt=0, description="Shares or contracts (> 0).")

    @model_validator(mode="before")
    @classmethod
    def _autocorrect(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = normalize_keys(data)
        if "quantity" in data:
            data["quantity"] = coerce_int(data["quantity"])
        if data.get("action"):
            data["action"] = match_enum(data["action"], ACTIONS)
        if data.get("instrument_type"):
            data["instrument_type"] = match_enum(data["instrument_type"], INSTRUMENT_TYPES)
        elif data.get("symbol"):
            data["instrument_type"] = "Equity Option" if is_option_symbol(str(data["symbol"])) else "Equity"
        return data

    @model_validator(mode="after")
    def _check(self) -> "OrderLeg":
        if self.action not in ACTIONS:
            raise ValueError(f"action must be one of {ACTIONS}. INCORRECT: {self.action!r}")
        if self.instrument_type not in INSTRUMENT_TYPES:
            raise ValueError(f"instrument_type must be one of {INSTRUMENT_TYPES}.")
        return self


class OrderRequest(BaseModel):
    """A complete order. Use preview_order to see fees/buying-power before place_order.

    CRITICAL: price is REQUIRED for Limit and Stop Limit orders.
    CORRECT (limit buy 100 AAPL @ 150):
      {"order_type":"Limit","time_in_force":"Day","price":150.0,
       "legs":[{"action":"Buy","symbol":"AAPL","quantity":100}]}
    INCORRECT (Limit with no price): {"order_type":"Limit","legs":[...]}
    """

    order_type: str = Field(description="Limit, Market, Stop, or Stop Limit.")
    time_in_force: str = Field(default="Day", description="Day, GTC, Ext, GTC Ext, or IOC.")
    legs: list[OrderLeg] = Field(min_length=1, max_length=4, description="1-4 legs.")
    price: Decimal | None = Field(default=None, description="Limit/stop price. Required for Limit/Stop Limit.")
    price_effect: str = Field(default="", description="Debit or Credit. Required for options/multi-leg.")

    @model_validator(mode="before")
    @classmethod
    def _autocorrect(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = normalize_keys(data)
        if data.get("order_type"):
            data["order_type"] = match_enum(data["order_type"], ORDER_TYPES)
        if data.get("time_in_force"):
            data["time_in_force"] = match_enum(data["time_in_force"], TIF)
        if data.get("price_effect"):
            data["price_effect"] = match_enum(data["price_effect"], PRICE_EFFECTS)
        return data

    @model_validator(mode="after")
    def _check(self) -> "OrderRequest":
        if self.order_type not in ORDER_TYPES:
            raise ValueError(f"order_type must be one of {ORDER_TYPES}. INCORRECT: {self.order_type!r}")
        if self.time_in_force not in TIF:
            raise ValueError(f"time_in_force must be one of {TIF}.")
        if self.order_type in ("Limit", "Stop Limit") and self.price is None:
            raise ValueError(
                f"price is required for {self.order_type} orders. "
                'CORRECT: {"order_type":"Limit","price":150.0,"legs":[...]}'
            )
        if self.price is not None and self.price <= 0:
            raise ValueError("price must be greater than 0.")
        is_multi_or_option = len(self.legs) > 1 or any(leg.instrument_type.endswith("Option") for leg in self.legs)
        if is_multi_or_option and not self.price_effect and self.order_type in ("Limit", "Stop Limit"):
            raise ValueError("price_effect ('Debit' or 'Credit') is required for option / multi-leg priced orders.")
        return self

    def to_api_body(self) -> dict:
        """Render the kebab-case JSON body the Tastytrade orders endpoint expects."""
        body: dict[str, Any] = {
            "order-type": self.order_type,
            "time-in-force": self.time_in_force,
            "legs": [
                {
                    "action": leg.action,
                    "symbol": leg.symbol,
                    "instrument-type": leg.instrument_type,
                    "quantity": leg.quantity,
                }
                for leg in self.legs
            ],
        }
        if self.price is not None:
            body["price"] = str(self.price)
        if self.price_effect:
            body["price-effect"] = self.price_effect
        return body
