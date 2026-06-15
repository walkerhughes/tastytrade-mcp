"""Server wiring and logging smoke tests."""

import pytest

from src.server import build_server


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_server_registers_twelve_tools(monkeypatch):
    monkeypatch.setenv("TT_CLIENT_ID", "x")
    monkeypatch.setenv("TT_SECRET", "x")
    monkeypatch.setenv("TT_REFRESH", "x")
    mcp = build_server()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert len(names) == 12
    assert {"list_accounts", "get_portfolio", "get_option_chain", "place_order"} <= names
