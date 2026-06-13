"""Shape order objects and dry-run (preview) responses."""

from .summarize import round_opt, to_float


def shape_order(o: dict) -> dict:
    """One compact order row with its legs."""
    legs = [
        {
            "symbol": leg.get("symbol"),
            "action": leg.get("action"),
            "quantity": to_float(leg.get("quantity")),
            "remaining_quantity": to_float(leg.get("remaining-quantity")),
            "instrument_type": leg.get("instrument-type"),
        }
        for leg in o.get("legs", [])
    ]
    return {
        "id": o.get("id"),
        "status": o.get("status"),
        "order_type": o.get("order-type"),
        "time_in_force": o.get("time-in-force"),
        "underlying_symbol": o.get("underlying-symbol"),
        "price": round_opt(to_float(o.get("price"))),
        "price_effect": o.get("price-effect"),
        "received_at": o.get("received-at"),
        "legs": legs,
    }


def shape_preview(data: dict) -> dict:
    """Extract the figures that matter from a dry-run: fees, BP effect, warnings."""
    bp = data.get("buying-power-effect", {}) or {}
    fees = data.get("fee-calculation", {}) or {}
    return {
        "buying_power_change": round_opt(to_float(bp.get("change-in-buying-power"))),
        "buying_power_effect": bp.get("change-in-buying-power-effect"),
        "new_buying_power": round_opt(to_float(bp.get("new-buying-power"))),
        "total_fees": round_opt(to_float(fees.get("total-fees"))),
        "warnings": [w.get("message", w) if isinstance(w, dict) else w for w in data.get("warnings", [])],
        "order_status": (data.get("order", {}) or {}).get("status"),
    }
