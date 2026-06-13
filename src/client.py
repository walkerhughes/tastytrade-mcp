"""TastyTrade API client with OAuth2 authentication."""

import asyncio
import os
import time

import httpx

from .infra.logging import get_logger


class TastyTradeClient:
    """Async HTTP client for the TastyTrade Open API.

    Uses OAuth2 refresh-token flow (POST /oauth/token) with automatic
    token refresh on expiry or 401 responses. Caches account list.
    """

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        base = base_url or os.environ.get("API_BASE_URL", "api.tastyworks.com")
        if not base.startswith("http"):
            base = f"https://{base}"
        self.base_url = base
        self._client_id = client_id or os.environ["TT_CLIENT_ID"]
        self._client_secret = client_secret or os.environ["TT_SECRET"]
        self._refresh_token = refresh_token or os.environ["TT_REFRESH"]
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self.customer_id: str | None = None
        self._accounts: list[dict] | None = None
        self._http: httpx.AsyncClient | None = None

    async def _http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "tastytrade-mcp/1.0",
                },
                timeout=30.0,
            )
        return self._http

    async def authenticate(self) -> None:
        """Obtain a new access token via OAuth2 refresh-token grant."""
        http = await self._http_client()
        resp = await http.post(
            "/oauth/token",
            content=(
                f"grant_type=refresh_token"
                f"&refresh_token={self._refresh_token}"
                f"&client_id={self._client_id}"
                f"&client_secret={self._client_secret}"
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 900)
        # Refresh 60s early to avoid edge-case expiry during a request
        self._token_expires_at = time.monotonic() + expires_in - 60
        http.headers["Authorization"] = f"Bearer {self._access_token}"

        # Extract customer ID from the JWT sub claim if present
        if not self.customer_id:
            try:
                import base64
                import json as _json

                payload = self._access_token.split(".")[1]
                # Pad base64
                payload += "=" * (4 - len(payload) % 4)
                claims = _json.loads(base64.urlsafe_b64decode(payload))
                self.customer_id = claims.get("sub")
            except Exception:
                pass

        self._accounts = None

    def _token_expired(self) -> bool:
        return time.monotonic() >= self._token_expires_at

    async def _ensure_auth(self) -> None:
        if self._access_token is None or self._token_expired():
            await self.authenticate()

    async def request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated API request.

        Auto-refreshes the token on 401 and retries, and retries 429/5xx responses
        with exponential backoff (up to 3 attempts) so transient rate limits don't
        surface to the model as hard failures.
        """
        await self._ensure_auth()
        http = await self._http_client()
        log = get_logger()

        backoffs = [0.5, 1.0, 2.0]
        for attempt in range(len(backoffs) + 1):
            start = time.monotonic()
            resp = await http.request(method, path, **kwargs)
            if resp.status_code == 401:
                await self.authenticate()
                resp = await http.request(method, path, **kwargs)
            dur_ms = round((time.monotonic() - start) * 1000, 1)
            log.debug("api_request method=%s path=%s status=%s ms=%s", method, path, resp.status_code, dur_ms)

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < len(backoffs):
                delay = backoffs[attempt]
                log.warning("api_retry path=%s status=%s attempt=%s delay=%s", path, resp.status_code, attempt, delay)
                await asyncio.sleep(delay)
                continue
            break

        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    async def get(self, path: str, **kwargs) -> dict:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> dict:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> dict:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs) -> dict:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> dict:
        return await self.request("DELETE", path, **kwargs)

    async def get_accounts(self) -> list[dict]:
        """Return cached account list, fetching on first call."""
        if self._accounts is None:
            data = await self.get("/customers/me/accounts")
            self._accounts = data["data"]["items"]
        return self._accounts

    async def get_default_account_number(self) -> str:
        """Return the first account number."""
        accounts = await self.get_accounts()
        return accounts[0]["account"]["account-number"]

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
