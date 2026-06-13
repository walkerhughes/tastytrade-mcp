"""Unit tests for TastyTrade API client."""

import httpx
import pytest

from src.client import TastyTradeClient

# Fixtures

# Minimal JWT with sub claim "U000123" (header.payload.signature)
# payload = base64url({"sub":"U000123","exp":9999999999})
_TEST_TOKEN = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJVMDAwMTIzIiwiZXhwIjo5OTk5OTk5OTk5fQ.sig"

OAUTH_RESPONSE = {
    "access_token": _TEST_TOKEN,
    "token_type": "Bearer",
    "expires_in": 900,
}

ACCOUNTS_RESPONSE = {
    "data": {
        "items": [
            {
                "account": {
                    "account-number": "5WT00001",
                    "account-type-name": "Individual",
                    "nickname": "Main",
                    "margin-or-cash": "Margin",
                    "is-closed": False,
                }
            },
            {
                "account": {
                    "account-number": "5WT00002",
                    "account-type-name": "IRA",
                    "nickname": "Retirement",
                    "margin-or-cash": "Cash",
                    "is-closed": False,
                }
            },
        ]
    }
}


def _mock_transport(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    """Create a mock transport that returns canned responses by path."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        for pattern, response in responses.items():
            if path.startswith(pattern):
                return response
        return httpx.Response(404, json={"error": {"message": "Not found"}})

    return httpx.MockTransport(handler)


def _make_client(**kwargs) -> TastyTradeClient:
    """Create a client with test defaults."""
    defaults = {
        "base_url": "https://api.test.com",
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "refresh_token": "test-refresh",
    }
    defaults.update(kwargs)
    return TastyTradeClient(**defaults)


@pytest.fixture
def client_env(monkeypatch):
    monkeypatch.setenv("TT_CLIENT_ID", "env-client-id")
    monkeypatch.setenv("TT_SECRET", "env-secret")
    monkeypatch.setenv("TT_REFRESH", "env-refresh")
    monkeypatch.setenv("API_BASE_URL", "api.test.com")


# Authentication


@pytest.mark.unit
@pytest.mark.asyncio
async def test_authenticate_sets_access_token():
    transport = _mock_transport({"/oauth/token": httpx.Response(200, json=OAUTH_RESPONSE)})
    client = _make_client()
    client._http = httpx.AsyncClient(base_url="https://api.test.com", transport=transport)

    await client.authenticate()

    assert client._access_token == _TEST_TOKEN
    assert client.customer_id == "U000123"
    assert "Bearer" in client._http.headers["Authorization"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_auth_calls_authenticate_once():
    transport = _mock_transport({"/oauth/token": httpx.Response(200, json=OAUTH_RESPONSE)})
    client = _make_client()
    client._http = httpx.AsyncClient(base_url="https://api.test.com", transport=transport)

    await client._ensure_auth()
    assert client._access_token == _TEST_TOKEN

    # Token not expired yet, so it should not re-authenticate
    old_expires = client._token_expires_at
    await client._ensure_auth()
    assert client._token_expires_at == old_expires


@pytest.mark.unit
@pytest.mark.asyncio
async def test_token_refresh_on_expiry():
    call_count = {"oauth": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        if path.startswith("/oauth/token"):
            call_count["oauth"] += 1
            return httpx.Response(200, json=OAUTH_RESPONSE)
        return httpx.Response(404)

    client = _make_client()
    client._http = httpx.AsyncClient(
        base_url="https://api.test.com",
        transport=httpx.MockTransport(handler),
    )

    await client._ensure_auth()
    assert call_count["oauth"] == 1

    # Force token expiry
    client._token_expires_at = 0
    await client._ensure_auth()
    assert call_count["oauth"] == 2


# Request handling


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_request():
    balances = {"data": {"net-liquidating-value": "50000.00"}}
    transport = _mock_transport(
        {
            "/oauth/token": httpx.Response(200, json=OAUTH_RESPONSE),
            "/accounts/5WT00001/balances": httpx.Response(200, json=balances),
        }
    )
    client = _make_client()
    client._http = httpx.AsyncClient(base_url="https://api.test.com", transport=transport)

    result = await client.get("/accounts/5WT00001/balances")
    assert result["data"]["net-liquidating-value"] == "50000.00"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auto_retry_on_401():
    call_count = {"oauth": 0, "balances": 0}
    balances = {"data": {"cash": "1000.00"}}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        if path.startswith("/oauth/token"):
            call_count["oauth"] += 1
            return httpx.Response(200, json=OAUTH_RESPONSE)
        if path.startswith("/accounts"):
            call_count["balances"] += 1
            if call_count["balances"] == 1:
                return httpx.Response(401, json={"error": {"message": "Unauthorized"}})
            return httpx.Response(200, json=balances)
        return httpx.Response(404)

    client = _make_client()
    client._http = httpx.AsyncClient(
        base_url="https://api.test.com",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get("/accounts/5WT00001/balances")
    assert result["data"]["cash"] == "1000.00"
    assert call_count["oauth"] == 2  # Initial auth + retry auth
    assert call_count["balances"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_204_returns_empty_dict():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        if path.startswith("/oauth/token"):
            return httpx.Response(200, json=OAUTH_RESPONSE)
        return httpx.Response(204)

    client = _make_client()
    client._http = httpx.AsyncClient(
        base_url="https://api.test.com",
        transport=httpx.MockTransport(handler),
    )

    result = await client.delete("/accounts/5WT/orders/123")
    assert result == {}


# Account helpers


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_accounts_caches():
    call_count = {"accounts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        if path.startswith("/oauth/token"):
            return httpx.Response(200, json=OAUTH_RESPONSE)
        if "/accounts" in path:
            call_count["accounts"] += 1
            return httpx.Response(200, json=ACCOUNTS_RESPONSE)
        return httpx.Response(404)

    client = _make_client()
    client._http = httpx.AsyncClient(
        base_url="https://api.test.com",
        transport=httpx.MockTransport(handler),
    )

    accounts = await client.get_accounts()
    assert len(accounts) == 2

    accounts2 = await client.get_accounts()
    assert accounts2 is accounts
    assert call_count["accounts"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_default_account_number():
    transport = _mock_transport(
        {
            "/oauth/token": httpx.Response(200, json=OAUTH_RESPONSE),
            "/customers/me/accounts": httpx.Response(200, json=ACCOUNTS_RESPONSE),
        }
    )
    client = _make_client()
    client._http = httpx.AsyncClient(base_url="https://api.test.com", transport=transport)

    acct = await client.get_default_account_number()
    assert acct == "5WT00001"


# Constructor


@pytest.mark.unit
def test_base_url_prepends_https():
    client = _make_client(base_url="api.test.com")
    assert client.base_url == "https://api.test.com"


@pytest.mark.unit
def test_base_url_keeps_existing_scheme():
    client = _make_client(base_url="https://api.test.com")
    assert client.base_url == "https://api.test.com"


@pytest.mark.unit
def test_constructor_uses_env(client_env):
    client = TastyTradeClient()
    assert client.base_url == "https://api.test.com"
    assert client._client_id == "env-client-id"
    assert client._client_secret == "env-secret"
    assert client._refresh_token == "env-refresh"
