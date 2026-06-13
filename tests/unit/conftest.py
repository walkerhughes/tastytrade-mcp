"""Shared fixtures for v2 tool unit tests."""

from typing import Any, Callable

import pytest

from src.tools import base


class FakeClient:
    """A scriptable stand-in for TastyTradeClient.

    ``routes`` maps a path substring to either a response dict or a zero-arg callable
    returning one. All requests are recorded in ``calls`` and write bodies in ``bodies``.
    """

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self.routes = routes or {}
        self.calls: list[tuple[str, str, dict]] = []
        self.bodies: list[tuple[str, str, Any]] = []
        self.customer_id = "U000123"

    async def get_default_account_number(self) -> str:
        return "5WT00001"

    def _resolve(self, method: str, path: str) -> dict:
        for key, resp in self.routes.items():
            if key in path:
                return resp() if callable(resp) else resp
        return {"data": {"items": []}}

    async def get(self, path: str, **kw) -> dict:
        self.calls.append(("GET", path, kw))
        return self._resolve("GET", path)

    async def post(self, path: str, **kw) -> dict:
        self.calls.append(("POST", path, kw))
        self.bodies.append(("POST", path, kw.get("json")))
        return self._resolve("POST", path)

    async def put(self, path: str, **kw) -> dict:
        self.calls.append(("PUT", path, kw))
        self.bodies.append(("PUT", path, kw.get("json")))
        return self._resolve("PUT", path)

    async def delete(self, path: str, **kw) -> dict:
        self.calls.append(("DELETE", path, kw))
        return self._resolve("DELETE", path)


@pytest.fixture
def install_client() -> Callable[[FakeClient], FakeClient]:
    """Install a FakeClient as the tool singleton and reset cache/state around the test."""
    base.reset_state()

    def _install(client: FakeClient) -> FakeClient:
        base._client = client  # type: ignore[assignment]
        base._cache = None  # force a fresh cache
        return client

    yield _install
    base.reset_state()
