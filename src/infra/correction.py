"""Correct common argument mistakes before the schema validates them.

Honeycomb found that quietly fixing predictable model errors, like renaming ``group_by`` to
``breakdowns`` or unwrapping an extra layer, was a big reliability win over rejecting them.
We do the same for Tastytrade arguments: key casing, enum casing, and numbers sent as
strings. The schemas call these from ``model_validator(mode="before")``.
"""

import re
from typing import Any

_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def normalize_key(key: str) -> str:
    """Turn ``order-type`` or ``orderType`` into ``order_type``."""
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
    """Turn ``"100"`` into ``100``, and leave non-numeric values for the validator to flag."""
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def match_enum(value: Any, choices: list[str]) -> Any:
    """Match an enum ignoring case and spacing, so ``"buy_to_open"`` matches ``"Buy to Open"``.

    Returns the canonical choice when one matches, otherwise the original value, so the
    validator can raise a clear error instead of accepting a wrong value silently.
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
