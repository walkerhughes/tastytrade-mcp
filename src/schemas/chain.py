"""Schema for the option-chain query, the nearest thing Tastytrade has to a query language.

Filtering a chain by expiration, days to expiration, strikes near the money, and type is
where the model most often gets stuck, so this schema does the most correction and checking.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..infra.correction import coerce_int, match_enum, normalize_keys
from ..schemas.common import validate_date


class ChainQuery(BaseModel):
    """Parameters for get_option_chain.

    Mode is implicit: omit ``expiration`` to discover available expirations (cheap),
    or pass one to get filtered, quote-enriched strikes plus a summary.
    """

    symbol: str = Field(description="Underlying ticker, e.g. 'SPY'.")
    expiration: str = Field(default="", description="YYYY-MM-DD. Omit to list expirations.")
    strikes_near: int = Field(default=10, ge=0, le=200, description="Strikes above & below ATM (0 = all).")
    dte_max: int | None = Field(default=None, ge=0, description="Only expirations within this many days.")
    option_type: Literal["", "call", "put"] = Field(default="", description="Filter to one side.")
    include_quotes: bool = Field(default=True, description="Enrich strikes with live quotes.")

    @model_validator(mode="before")
    @classmethod
    def _autocorrect(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = normalize_keys(data)
        # Common aliases the model reaches for.
        if "expiration_date" in data and "expiration" not in data:
            data["expiration"] = data.pop("expiration_date")
        if "type" in data and "option_type" not in data:
            data["option_type"] = data.pop("type")
        if data.get("option_type"):
            data["option_type"] = match_enum(str(data["option_type"]), ["call", "put", ""]).lower()
        for key in ("strikes_near", "dte_max"):
            if key in data and data[key] is not None:
                data[key] = coerce_int(data[key])
        return data

    @model_validator(mode="after")
    def _check(self) -> "ChainQuery":
        validate_date(self.expiration, "expiration")
        return self
