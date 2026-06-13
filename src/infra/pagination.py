"""Shared pagination parameters merged into every list-style tool.

The Honeycomb ``PaginationSchema`` analogue: a single, consistent set of paging knobs
(``page``, ``limit``, ``sort_by``, ``sort_order``, ``search``) so the model learns one
pattern that works across tools.
"""

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Standard paging/search/sort knobs. Defaults keep responses small."""

    page: int = Field(default=1, ge=1, description="1-based page number.")
    limit: int = Field(default=25, ge=1, le=500, description="Items per page (max 500).")
    sort_by: str = Field(default="", description="Field name to sort by; empty keeps source order.")
    sort_order: str = Field(default="desc", description="'asc' or 'desc'.")
    search: str = Field(default="", description="Case-insensitive substring filter across fields.")
