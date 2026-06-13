"""Shape balances, positions, and net-liq history into compact, summarized forms."""

from .summarize import downsample, group_sum, max_drawdown, round_opt, to_float

_DIR_SIGN = {"Long": 1, "Short": -1, "Zero": 0}


def shape_balances(data: dict) -> dict:
    """Project the verbose balances payload down to the figures a trader actually reads."""
    g = data.get
    return {
        "net_liquidating_value": round_opt(to_float(g("net-liquidating-value"))),
        "cash_balance": round_opt(to_float(g("cash-balance"))),
        "equity_buying_power": round_opt(to_float(g("equity-buying-power"))),
        "derivative_buying_power": round_opt(to_float(g("derivative-buying-power"))),
        "maintenance_requirement": round_opt(to_float(g("maintenance-requirement"))),
        "cash_available_to_withdraw": round_opt(to_float(g("cash-available-to-withdraw"))),
        "pending_cash": round_opt(to_float(g("pending-cash"))),
    }


def shape_position(pos: dict) -> dict:
    """One position with computed market value and unrealized P/L where data allows."""
    qty = to_float(pos.get("quantity")) or 0.0
    sign = _DIR_SIGN.get(pos.get("quantity-direction", "Long"), 1)
    multiplier = to_float(pos.get("multiplier")) or 1.0
    avg_open = to_float(pos.get("average-open-price"))
    mark = to_float(pos.get("mark-price")) or to_float(pos.get("mark"))
    close = to_float(pos.get("close-price"))
    ref = mark if mark is not None else close

    value = pnl = pnl_pct = None
    if ref is not None:
        value = round(ref * qty * multiplier * (sign or 1), 2)
    if ref is not None and avg_open is not None and qty:
        pnl = round((ref - avg_open) * qty * multiplier * sign, 2)
        cost = abs(avg_open * qty * multiplier)
        pnl_pct = round((pnl / cost) * 100, 2) if cost else None

    return {
        "symbol": pos.get("symbol"),
        "instrument_type": pos.get("instrument-type"),
        "underlying_symbol": pos.get("underlying-symbol"),
        "quantity": qty,
        "direction": pos.get("quantity-direction"),
        "avg_open_price": round_opt(avg_open),
        "mark": round_opt(ref),
        "value": value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }


def shape_portfolio(balances: dict, positions: list[dict]) -> dict:
    """Combine balances + positions into one response with a P/L rollup summary."""
    shaped = [shape_position(p) for p in positions]
    total_pnl = round(sum(p["pnl"] for p in shaped if p["pnl"] is not None), 2)
    total_value = round(sum(p["value"] for p in shaped if p["value"] is not None), 2)
    exposure = group_sum(shaped, "underlying_symbol", "value")
    longs = sum(1 for p in shaped if (p["direction"] == "Long"))
    shorts = sum(1 for p in shaped if (p["direction"] == "Short"))

    return {
        "summary": {
            "net_liquidating_value": shape_balances(balances)["net_liquidating_value"],
            "position_count": len(shaped),
            "long_positions": longs,
            "short_positions": shorts,
            "total_position_value": total_value,
            "total_unrealized_pnl": total_pnl,
            "exposure_by_underlying": exposure,
        },
        "balances": shape_balances(balances),
        "positions": shaped,
    }


def shape_history(snapshots: list[dict], max_points: int = 30) -> dict:
    """Downsample net-liq history and compute start/end/change/drawdown stats."""
    points: list[dict] = []
    values: list[float] = []
    for s in snapshots:
        value = to_float(s.get("close") or s.get("net-liquidating-value"))
        if value is None:
            continue
        rounded = round(value, 2)
        values.append(rounded)
        points.append({"time": s.get("time") or s.get("snapshot-date"), "value": rounded})

    if not points:
        return {"summary": {"points": 0}, "series": []}

    start, end = values[0], values[-1]
    change = round(end - start, 2)
    change_pct = round((change / start) * 100, 2) if start else None

    return {
        "summary": {
            "points": len(points),
            "start_value": start,
            "end_value": end,
            "change": change,
            "change_pct": change_pct,
            "high": max(values),
            "low": min(values),
            "max_drawdown_pct": round(max_drawdown(values) * 100, 2),
        },
        "series": downsample(points, max_points),
    }
