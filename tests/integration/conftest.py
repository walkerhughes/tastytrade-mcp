"""Integration fixtures: a real TastyTradeClient wired to the in-process mock API."""

import httpx
import pytest

from src.client import TastyTradeClient
from src.tools import base
from tests.fixtures.mock_api.app import build_app


@pytest.fixture
def mock_app():
    return build_app()


@pytest.fixture
def tt_client(mock_app, monkeypatch):
    """Install a client backed by the mock API as the tool singleton."""
    monkeypatch.setenv("TT_CLIENT_ID", "test")
    monkeypatch.setenv("TT_SECRET", "test")
    monkeypatch.setenv("TT_REFRESH", "test")
    transport = httpx.ASGITransport(app=mock_app)
    client = TastyTradeClient(base_url="http://mock.local", transport=transport)
    base.reset_state()
    base._client = client
    base._cache = None
    yield client
    base.reset_state()
