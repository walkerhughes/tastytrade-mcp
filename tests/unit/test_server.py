import json
from unittest.mock import MagicMock, patch

import pytest

from src.server import (
    _get_client,
    _reset_client,
    get_accounts,
    get_balances,
    get_equity_info,
    get_live_orders,
    get_market_metrics,
    get_option_chain,
    get_order_history,
    get_positions,
    get_quotes,
    tastytrade_api_request,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset the singleton before each test."""
    _reset_client()
    yield
    _reset_client()


@pytest.fixture()
def mock_api(monkeypatch):
    """Set up OAuth2 env vars and mock the Tastytrade client."""
    monkeypatch.setenv("TT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("TT_SECRET", "test-secret")
    monkeypatch.setenv("TT_REFRESH", "test-refresh-token")
    mock_client = MagicMock()
    with patch("src.server.Tastytrade") as mock_cls:
        mock_cls.return_value = mock_client
        yield mock_client.api


@pytest.fixture()
def mock_api_login(monkeypatch):
    """Set up legacy login env vars and mock the Tastytrade client."""
    monkeypatch.setenv("TT_USERNAME", "testuser")
    monkeypatch.setenv("TT_PASSWORD", "testpass")
    monkeypatch.delenv("TT_CLIENT_ID", raising=False)
    monkeypatch.delenv("TT_SECRET", raising=False)
    monkeypatch.delenv("TT_REFRESH", raising=False)
    mock_client = MagicMock()
    with patch("src.server.Tastytrade") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.login.return_value = mock_client
        mock_cls.return_value = mock_instance
        yield mock_client.api


@pytest.mark.unit
class TestGetClient:
    def test_oauth2_preferred(self, mock_api):
        """Client uses OAuth2 when credentials are present."""
        _get_client()
        # Second call reuses singleton
        assert _get_client() is _get_client()

    def test_login_fallback(self, mock_api_login):
        """Client falls back to login() when OAuth2 creds are missing."""
        _get_client()
        assert _get_client() is _get_client()

    def test_reset_client(self, mock_api):
        """_reset_client clears the singleton."""
        _get_client()
        _reset_client()
        with patch("src.server.Tastytrade") as mock_cls:
            mock_cls.return_value = MagicMock()
            _get_client()
            mock_cls.assert_called_once()


def _wrap(data):
    """Simulate the Tastytrade API data envelope."""
    return {"data": data}


@pytest.mark.unit
class TestGetAccounts:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"items": [{"account-number": "5WX12345"}]})
        result = json.loads(get_accounts())
        assert result["items"][0]["account-number"] == "5WX12345"
        mock_api.get.assert_called_once_with("/customers/me/accounts")

    def test_error(self, mock_api):
        mock_api.get.side_effect = RuntimeError("auth failed")
        result = json.loads(get_accounts())
        assert "RuntimeError" in result["error"]

    def test_sdk_error(self, mock_api):
        """SDK errors (BaseException subclass) are caught."""
        from tastytrade_sdk.api import Forbidden

        mock_api.get.side_effect = Forbidden("Forbidden", 403, {"code": "not_permitted", "message": "denied"})
        result = json.loads(get_accounts())
        assert "Forbidden" in result["error"]


@pytest.mark.unit
class TestGetBalances:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"net-liquidating-value": "50000.00"})
        result = json.loads(get_balances("5WX12345"))
        assert result["net-liquidating-value"] == "50000.00"
        mock_api.get.assert_called_once_with("/accounts/5WX12345/balances")

    def test_error(self, mock_api):
        mock_api.get.side_effect = ValueError("bad account")
        result = json.loads(get_balances("INVALID"))
        assert "ValueError" in result["error"]


@pytest.mark.unit
class TestGetPositions:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"items": [{"symbol": "SPY"}]})
        result = json.loads(get_positions("5WX12345"))
        assert result["items"][0]["symbol"] == "SPY"
        mock_api.get.assert_called_once_with("/accounts/5WX12345/positions")


@pytest.mark.unit
class TestGetLiveOrders:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"items": []})
        result = json.loads(get_live_orders("5WX12345"))
        assert result["items"] == []
        mock_api.get.assert_called_once_with("/accounts/5WX12345/orders/live")


@pytest.mark.unit
class TestGetOrderHistory:
    def test_no_dates(self, mock_api):
        mock_api.get.return_value = _wrap({"items": []})
        get_order_history("5WX12345")
        mock_api.get.assert_called_once_with("/accounts/5WX12345/orders", params=None)

    def test_with_dates(self, mock_api):
        mock_api.get.return_value = _wrap({"items": []})
        get_order_history("5WX12345", start_date="2024-01-01", end_date="2024-12-31")
        mock_api.get.assert_called_once_with(
            "/accounts/5WX12345/orders",
            params={"start-date": "2024-01-01", "end-date": "2024-12-31"},
        )

    def test_error(self, mock_api):
        mock_api.get.side_effect = Exception("timeout")
        result = json.loads(get_order_history("5WX12345"))
        assert "error" in result


@pytest.mark.unit
class TestGetEquityInfo:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"items": [{"symbol": "AAPL"}]})
        result = json.loads(get_equity_info(["AAPL", "SPY"]))
        assert result["items"][0]["symbol"] == "AAPL"
        mock_api.get.assert_called_once_with(
            "/instruments/equities",
            params=[("symbol[]", "AAPL"), ("symbol[]", "SPY")],
        )


@pytest.mark.unit
class TestGetOptionChain:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"expirations": []})
        result = json.loads(get_option_chain("SPY"))
        assert result["expirations"] == []
        mock_api.get.assert_called_once_with("/option-chains/SPY/nested")


@pytest.mark.unit
class TestGetQuotes:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"items": [{"symbol": "SPY", "implied-volatility": 0.20}]})
        result = json.loads(get_quotes(["SPY"]))
        assert result["items"][0]["symbol"] == "SPY"
        mock_api.get.assert_called_once_with(
            "/market-metrics",
            params=[("symbols", "SPY")],
        )


@pytest.mark.unit
class TestGetMarketMetrics:
    def test_success(self, mock_api):
        mock_api.get.return_value = _wrap({"items": [{"iv-rank": 0.45}]})
        result = json.loads(get_market_metrics(["SPY"]))
        assert result["items"][0]["iv-rank"] == 0.45
        mock_api.get.assert_called_once_with(
            "/market-metrics",
            params=[("symbols", "SPY")],
        )


@pytest.mark.unit
class TestTastytradeApiRequest:
    def test_get(self, mock_api):
        mock_api.get.return_value = {"ok": True}
        result = json.loads(tastytrade_api_request("GET", "/some/path"))
        assert result["ok"] is True
        mock_api.get.assert_called_once_with("/some/path", params=None)

    def test_post_with_data(self, mock_api):
        mock_api.post.return_value = _wrap({"created": True})
        result = json.loads(tastytrade_api_request("POST", "/orders", data={"qty": 1}))
        assert result["created"] is True
        mock_api.post.assert_called_once_with("/orders", params=None, data={"qty": 1})

    def test_put(self, mock_api):
        mock_api.put.return_value = _wrap({"updated": True})
        tastytrade_api_request("PUT", "/path", data={"x": 1})
        mock_api.put.assert_called_once_with("/path", params=None, data={"x": 1})

    def test_patch(self, mock_api):
        mock_api.patch.return_value = _wrap({})
        tastytrade_api_request("PATCH", "/path", data={"x": 1})
        mock_api.patch.assert_called_once_with("/path", params=None, data={"x": 1})

    def test_delete(self, mock_api):
        mock_api.delete.return_value = _wrap({})
        tastytrade_api_request("DELETE", "/path")
        mock_api.delete.assert_called_once_with("/path", params=None)

    def test_unknown_method(self, mock_api):
        result = json.loads(tastytrade_api_request("TRACE", "/path"))
        assert "Unknown method" in result["error"]

    def test_sdk_error(self, mock_api):
        """SDK errors (BaseException subclass) are caught."""
        from tastytrade_sdk.api import ServerError

        mock_api.get.side_effect = ServerError("Internal Server Error", 500, {"code": "err", "message": "fail"})
        result = json.loads(tastytrade_api_request("GET", "/fail"))
        assert "ServerError" in result["error"]
