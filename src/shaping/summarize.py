"""Small numeric/aggregation helpers used to build per-tool ``summary`` blocks.

Server-side summaries are the core token-saving move: the model usually wants the
aggregate (total P/L, IV range, top strikes) and can skip the raw rows entirely.
"""

import statistics
from typing import Any, Callable, Iterable


def to_float(value: Any, default: float | None = None) -> float | None:
    """Coerce Tastytrade's decimal strings to float; return default on failure."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def round_opt(value: float | None, ndigits: int = 2) -> float | None:
    return round(value, ndigits) if value is not None else None


def stats(values: Iterable[Any]) -> dict[str, float] | None:
    """min/max/avg/median/sum/stdev over a sequence, ignoring non-numeric entries."""
    nums = [v for v in (to_float(x) for x in values) if v is not None]
    if not nums:
        return None
    return {
        "min": round(min(nums), 4),
        "max": round(max(nums), 4),
        "avg": round(sum(nums) / len(nums), 4),
        "median": round(statistics.median(nums), 4),
        "sum": round(sum(nums), 4),
        "stdev": round(statistics.pstdev(nums), 4) if len(nums) > 1 else 0.0,
        "count": len(nums),
    }


def top_n(items: list[dict], key: str, n: int = 5, label_keys: tuple[str, ...] = ()) -> list[dict]:
    """Return the ``n`` items with the highest numeric ``key``, projected to label+value."""
    scored: list[tuple[float, dict]] = []
    for it in items:
        v = to_float(it.get(key))
        if v is not None:
            scored.append((v, it))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    out: list[dict] = []
    for value, it in scored[:n]:
        row: dict[str, Any] = {k: it.get(k) for k in label_keys if k in it}
        row[key] = value
        out.append(row)
    return out


def downsample(points: list[Any], max_points: int) -> list[Any]:
    """Evenly thin a series to at most ``max_points`` items, always keeping the last."""
    if len(points) <= max_points or max_points <= 0:
        return points
    step = len(points) / max_points
    idx = sorted({min(len(points) - 1, int(i * step)) for i in range(max_points)})
    if idx[-1] != len(points) - 1:
        idx[-1] = len(points) - 1
    return [points[i] for i in idx]


def max_drawdown(values: list[float]) -> float:
    """Largest peak-to-trough drop as a fraction (0..1) of the running peak."""
    peak = float("-inf")
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, (v - peak) / peak)
    return round(abs(worst), 4)


def group_sum(
    items: list[dict],
    group_key: str,
    value_key: str,
    transform: Callable[[float], float] | None = None,
) -> dict[str, float]:
    """Sum ``value_key`` grouped by ``group_key`` (e.g. exposure by underlying)."""
    out: dict[str, float] = {}
    for it in items:
        g = it.get(group_key)
        v = to_float(it.get(value_key))
        if g is None or v is None:
            continue
        out[str(g)] = round(out.get(str(g), 0.0) + (transform(v) if transform else v), 2)
    return out
