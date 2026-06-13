"""In-process / sidecar mock of the Tastytrade Open API for deterministic tests & benchmarks."""

from .app import build_app

__all__ = ["build_app"]
