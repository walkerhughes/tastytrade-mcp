"""Shape quotes and volatility metrics into a compact per-symbol snapshot."""

from typing import Any

from .summarize import round_opt, to_float


def shape_quote(q: dict) -> dict:
    """Minimal quote: bid/ask/last/mid + day move."""
    bid = to_float(q.get("bid"))
    ask = to_float(q.get("ask"))
    last = to_float(q.get("last"))
    mid = to_float(q.get("mid"))
    if mid is None and bid is not None and ask is not None:
        mid = round((bid + ask) / 2, 4)
    prev_close = to_float(q.get("prev-close") or q.get("close"))
    day_change = day_change_pct = None
    if last is not None and prev_close is not None:
        day_change = round(last - prev_close, 4)
        day_change_pct = round((day_change / prev_close) * 100, 2) if prev_close else None
    return {
        "symbol": q.get("symbol"),
        "bid": round_opt(bid, 4),
        "ask": round_opt(ask, 4),
        "last": round_opt(last, 4),
        "mid": round_opt(mid, 4),
        "volume": to_float(q.get("volume")),
        "day_change": day_change,
        "day_change_pct": day_change_pct,
    }


def shape_metrics(m: dict) -> dict:
    """Minimal volatility/liquidity metrics."""
    return {
        "symbol": m.get("symbol"),
        "iv_index": round_opt(to_float(m.get("implied-volatility-index")), 4),
        "iv_rank": round_opt(to_float(m.get("implied-volatility-index-rank")), 2),
        "iv_percentile": round_opt(to_float(m.get("implied-volatility-percentile")), 2),
        "liquidity_rating": m.get("liquidity-rating"),
        "beta": round_opt(to_float(m.get("beta")), 3),
    }


def shape_market_data(
    symbol: str,
    quote: dict | None,
    metrics: dict | None,
    dividends: list[dict] | None,
    earnings: list[dict] | None,
    instrument: dict | None,
) -> dict:
    """Merge the requested facets for one symbol into a single object."""
    out: dict[str, Any] = {"symbol": symbol}
    if quote is not None:
        out["quote"] = shape_quote(quote)
    if metrics is not None:
        out["metrics"] = shape_metrics(metrics)
    if dividends is not None:
        latest = dividends[0] if dividends else None
        out["latest_dividend"] = (
            {
                "amount": round_opt(to_float(latest.get("amount"))),
                "ex_date": latest.get("occurred-date") or latest.get("ex-dividend-date"),
            }
            if latest
            else None
        )
    if earnings is not None:
        nxt = earnings[0] if earnings else None
        out["next_earnings"] = (
            {"date": nxt.get("occurred-date") or nxt.get("report-date"), "eps": nxt.get("eps")} if nxt else None
        )
    if instrument is not None:
        out["instrument"] = {
            "description": instrument.get("description"),
            "exchange": instrument.get("listed-market") or instrument.get("exchange"),
            "is_active": instrument.get("active"),
        }
    return out
