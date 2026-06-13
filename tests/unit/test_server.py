"""Server wiring and logging smoke tests."""

import pytest

from src.infra.logging import configure_logging, log_tool_call
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


@pytest.mark.unit
def test_log_tool_call_records_and_reraises():
    configure_logging("DEBUG")
    with log_tool_call("demo") as rec:
        rec["bytes"] = 10
    assert rec["bytes"] == 10

    with pytest.raises(ValueError):
        with log_tool_call("demo_err"):
            raise ValueError("boom")
