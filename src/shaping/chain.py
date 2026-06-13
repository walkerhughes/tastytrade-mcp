"""Shape nested option chains: expirations listing, strike filtering, quote enrichment.

This is the curated-tool centerpiece. The nested chain endpoint carries no quotes, so we
filter strikes first, then enrich only the survivors with a single batched quote call —
the token win and the analytical value-add live here.
"""

from typing import Any

from .summarize import round_opt, to_float, top_n


def list_expirations(items: list[dict], dte_max: int | None = None) -> list[dict]:
    """Compact expirations listing for chain discovery (no expiration requested)."""
    out = []
    for item in items:
        for exp in item.get("expirations", []):
            dte = exp.get("days-to-expiration")
            if dte_max is not None and dte is not None and dte > dte_max:
                continue
            out.append(
                {
                    "expiration_date": exp.get("expiration-date"),
                    "days_to_expiration": dte,
                    "expiration_type": exp.get("expiration-type"),
                    "strikes_count": len(exp.get("strikes", [])),
                }
            )
    return out


def select_strikes(items: list[dict], expiration: str, strikes_near: int) -> tuple[dict | None, list[dict]]:
    """Find the requested expiration and trim to ``strikes_near`` around the middle.

    Returns (expiration_meta, raw_strikes). strikes_near==0 keeps all strikes.
    """
    for item in items:
        for exp in item.get("expirations", []):
            if exp.get("expiration-date") != expiration:
                continue
            strikes = exp.get("strikes", [])
            if strikes_near > 0 and strikes:
                mid = len(strikes) // 2
                lo = max(0, mid - strikes_near)
                hi = min(len(strikes), mid + strikes_near + 1)
                strikes = strikes[lo:hi]
            meta = {
                "expiration_date": exp.get("expiration-date"),
                "days_to_expiration": exp.get("days-to-expiration"),
            }
            return meta, strikes
    return None, []


def collect_symbols(strikes: list[dict], option_type: str) -> list[str]:
    """Gather the OCC symbols to quote for the selected strikes/side."""
    syms: list[str] = []
    for s in strikes:
        if option_type in ("", "call") and s.get("call"):
            syms.append(s["call"])
        if option_type in ("", "put") and s.get("put"):
            syms.append(s["put"])
    return syms


def shape_chain(
    meta: dict,
    strikes: list[dict],
    quotes_by_symbol: dict[str, dict],
    option_type: str,
) -> dict:
    """Build enriched strike rows + a summary (ATM, ranges, top volume / open interest)."""
    rows: list[dict] = []
    flat_for_stats: list[dict] = []
    for s in strikes:
        strike_price = to_float(s.get("strike-price"))
        row: dict[str, Any] = {"strike": round_opt(strike_price)}
        for side in ("call", "put"):
            if option_type and option_type != side:
                continue
            occ = s.get(side)
            q = quotes_by_symbol.get(occ, {}) if occ else {}
            leg = {
                "symbol": occ,
                "bid": round_opt(to_float(q.get("bid")), 4),
                "ask": round_opt(to_float(q.get("ask")), 4),
                "mid": round_opt(to_float(q.get("mid")), 4),
                "volume": to_float(q.get("volume")),
                "open_interest": to_float(q.get("open-interest")),
                "iv": round_opt(to_float(q.get("implied-volatility")), 4),
            }
            row[side] = leg
            flat_for_stats.append({"strike": strike_price, **leg})
        rows.append(row)

    strike_prices = [r["strike"] for r in rows if r["strike"] is not None]
    ivs = [f["iv"] for f in flat_for_stats if f.get("iv") is not None]
    atm = _nearest_atm(strike_prices, quotes_by_symbol, strikes, option_type)

    summary = {
        "expiration_date": meta.get("expiration_date"),
        "days_to_expiration": meta.get("days_to_expiration"),
        "n_strikes": len(rows),
        "strike_range": [min(strike_prices), max(strike_prices)] if strike_prices else None,
        "atm_strike": atm,
        "iv_range": [min(ivs), max(ivs)] if ivs else None,
        "top_volume": top_n(flat_for_stats, "volume", n=5, label_keys=("strike", "symbol")),
        "top_open_interest": top_n(flat_for_stats, "open_interest", n=5, label_keys=("strike", "symbol")),
    }
    return {"summary": summary, "strikes": rows}


def _nearest_atm(strike_prices: list[float], quotes: dict, strikes: list[dict], option_type: str) -> float | None:
    """Estimate ATM strike as the one whose call & put mids are closest (put-call parity proxy)."""
    if not strike_prices:
        return None
    best_strike = None
    best_gap = None
    for s in strikes:
        sp = to_float(s.get("strike-price"))
        cq = quotes.get(s.get("call"), {})
        pq = quotes.get(s.get("put"), {})
        cm, pm = to_float(cq.get("mid")), to_float(pq.get("mid"))
        if sp is None or cm is None or pm is None:
            continue
        gap = abs(cm - pm)
        if best_gap is None or gap < best_gap:
            best_gap, best_strike = gap, sp
    # Fall back to the median strike if no quotes were available.
    return round_opt(best_strike) if best_strike is not None else round_opt(strike_prices[len(strike_prices) // 2])
