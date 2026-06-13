"""Shape transactions with a cash/fee summary."""

from .summarize import round_opt, to_float

_EFFECT_SIGN = {"Credit": 1, "Debit": -1, "None": 0, "": 0}


def _signed(value: object, effect: object) -> float | None:
    v = to_float(value)
    if v is None:
        return None
    return v * _EFFECT_SIGN.get(str(effect), 1)


def shape_transaction(t: dict) -> dict:
    """One compact transaction row."""
    fees = sum(
        to_float(t.get(k)) or 0.0
        for k in ("commission", "clearing-fees", "regulatory-fees", "proprietary-index-option-fees")
    )
    return {
        "id": t.get("id"),
        "type": t.get("transaction-type"),
        "sub_type": t.get("transaction-sub-type"),
        "symbol": t.get("symbol"),
        "underlying_symbol": t.get("underlying-symbol"),
        "quantity": to_float(t.get("quantity")),
        "price": round_opt(to_float(t.get("price"))),
        "net_value": _signed(t.get("net-value"), t.get("net-value-effect")),
        "fees": round(fees, 2),
        "executed_at": t.get("executed-at"),
        "description": t.get("description"),
    }


def summarize_transactions(rows: list[dict]) -> dict:
    """Net cash effect, total fees, counts by type, and the effective date span."""
    net_cash = round(sum(r["net_value"] for r in rows if r["net_value"] is not None), 2)
    total_fees = round(sum(r["fees"] for r in rows if r["fees"] is not None), 2)
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["type"] or "Unknown"] = by_type.get(r["type"] or "Unknown", 0) + 1
    times = [r["executed_at"] for r in rows if r["executed_at"]]
    return {
        "count": len(rows),
        "net_cash_effect": net_cash,
        "total_fees": total_fees,
        "by_type": by_type,
        "date_range": [min(times), max(times)] if times else None,
    }
