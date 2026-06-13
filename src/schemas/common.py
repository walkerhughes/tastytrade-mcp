"""Shared field types and validators used across tool schemas."""

import re

# OCC-style option symbols look like "AAPL  260116C00150000" (root + 6-digit date + C/P + strike).
_OCC_RE = re.compile(r"^[A-Z]{1,6}\s*\d{6}[CP]\d{8}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_option_symbol(symbol: str) -> bool:
    """True if ``symbol`` looks like an OCC option symbol rather than an equity ticker."""
    s = symbol.strip().upper()
    if _OCC_RE.match(s):
        return True
    # Compact OCC (no padding) still has digits in the back half and is long.
    return len(s) > 8 and any(c.isdigit() for c in s) and s[-1].isdigit()


def validate_date(value: str, field: str = "date") -> str:
    """Validate a YYYY-MM-DD string; raise ValueError with guidance otherwise."""
    if value and not _DATE_RE.match(value):
        raise ValueError(f"{field} must be YYYY-MM-DD (got {value!r}). CORRECT: '2026-01-17'")
    return value
