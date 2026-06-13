"""Auto-correction of common LLM argument mistakes, applied *before* validation.

Honeycomb's biggest reliability win was silently fixing predictable model errors
(``group_by``→``breakdowns``, ``field``→``column``, un-nesting wrappers) instead of
rejecting them. We do the same for Tastytrade argument shapes: key casing, enum casing,
and stringified numbers. Schemas call these in ``model_validator(mode="before")``.
"""

import re
from typing import Any

_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def normalize_key(key: str) -> str:
    """``order-type`` / ``orderType`` / ``order_type`` → ``order_type``."""
    key = key.replace("-", "_")
    key = _CAMEL_RE.sub("_", key)
    return key.lower()


def normalize_keys(data: Any) -> Any:
    """Recursively snake_case all dict keys."""
    if isinstance(data, dict):
        return {normalize_key(str(k)): normalize_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [normalize_keys(v) for v in data]
    return data


def coerce_int(value: Any) -> Any:
    """``"100"`` → ``100``; leave non-numeric values untouched for the validator to flag."""
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def match_enum(value: Any, choices: list[str]) -> Any:
    """Case/spacing-insensitive enum match: ``"buy_to_open"`` → ``"Buy to Open"``.

    Returns the canonical choice if a normalized match exists, else the original value
    (so the validator produces a guided error rather than a silent wrong value).
    """
    if not isinstance(value, str):
        return value

    def canon(s: str) -> str:
        return re.sub(r"[\s_-]+", " ", s.strip().lower())

    target = canon(value)
    for choice in choices:
        if canon(choice) == target:
            return choice
    return value


def unwrap(data: Any, *keys: str) -> Any:
    """Un-nest a single-key wrapper the model sometimes adds, e.g. ``{"order": {...}}``."""
    if isinstance(data, dict) and len(data) == 1:
        only_key = next(iter(data))
        if only_key in keys:
            return data[only_key]
    return data
