"""Guided error handling — the Honeycomb ``handleToolError`` analogue.

Tools never leak tracebacks to the model. Instead every failure becomes a small JSON
object: a human-readable ``error`` plus a ``suggestions`` array of concrete next steps
(often containing CORRECT/INCORRECT examples). This is what stops the model's
fail → tweak → give-up doom loop.
"""

import functools
import json
from typing import Awaitable, Callable

import httpx

from .logging import get_logger

try:  # pydantic is a hard dep in v2, but keep import resilient for partial installs
    from pydantic import ValidationError
except Exception:  # pragma: no cover
    ValidationError = ()  # type: ignore[assignment,misc]


def error_response(message: str, suggestions: list[str] | None = None, **extra: object) -> str:
    """Render a guided error as a JSON string (the uniform tool failure shape)."""
    payload: dict[str, object] = {"error": message}
    if suggestions:
        payload["suggestions"] = suggestions
    payload.update(extra)
    return json.dumps(payload, indent=2, default=str)


# HTTP status → (human message, next-step suggestions). 422 is parsed from the body.
_HTTP_GUIDANCE: dict[int, tuple[str, list[str]]] = {
    401: (
        "Authentication failed.",
        [
            "Verify TT_CLIENT_ID, TT_SECRET, and TT_REFRESH are set and current.",
            "The refresh token may have been revoked — re-authorize the OAuth client.",
        ],
    ),
    403: (
        "Not authorized for this resource.",
        ["This account or feature may not be enabled for your login.", "Check the account with list_accounts."],
    ),
    404: (
        "Resource not found.",
        [
            "Verify the symbol with search_symbols.",
            "Verify the account number with list_accounts.",
            "Verify the order id with list_orders.",
        ],
    ),
    429: (
        "Rate limited by the Tastytrade API.",
        ["Wait a few seconds and retry.", "Batch symbols into a single call where the tool supports it."],
    ),
}


def _parse_422(body: object) -> tuple[str, list[str]]:
    """Tastytrade 422 bodies carry {"error": {"code","message","errors":[...]}}."""
    suggestions: list[str] = []
    message = "The request was rejected as invalid (422)."
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            if err.get("message"):
                message = f"Tastytrade rejected the request: {err['message']}"
            for sub in err.get("errors", []) or []:
                if isinstance(sub, dict):
                    detail = sub.get("message") or sub.get("reason")
                    if detail:
                        suggestions.append(str(detail))
                else:
                    suggestions.append(str(sub))
    if not suggestions:
        suggestions = ["Re-check required fields (price for Limit orders, price_effect for options)."]
    return message, suggestions


def _from_http_error(exc: httpx.HTTPStatusError) -> str:
    status = exc.response.status_code
    if status == 422:
        try:
            body = exc.response.json()
        except Exception:
            body = None
        message, suggestions = _parse_422(body)
    else:
        message, suggestions = _HTTP_GUIDANCE.get(
            status, (f"The API returned HTTP {status}.", ["Retry, or simplify the request."])
        )
    return error_response(message, suggestions, status_code=status)


def _from_validation_error(exc: "ValidationError") -> str:
    suggestions: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        suggestions.append(f"{loc}: {msg}" if loc else msg)
    return error_response(
        "The tool arguments did not pass validation.",
        suggestions or ["Re-read the tool docstring for the required argument shape."],
    )


def guarded_tool(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """Wrap an async tool so any failure returns a guided error string, never a traceback."""

    @functools.wraps(func)
    async def wrapper(*args: object, **kwargs: object) -> str:
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            get_logger().warning("http_error tool=%s status=%s", func.__name__, exc.response.status_code)
            return _from_http_error(exc)
        except ValidationError as exc:  # type: ignore[misc]
            return _from_validation_error(exc)
        except httpx.HTTPError as exc:  # network/timeout
            return error_response(
                f"Network error contacting Tastytrade: {type(exc).__name__}.",
                ["Check connectivity to the API host.", "Retry in a moment."],
            )
        except (KeyError, ValueError, TypeError) as exc:
            get_logger().warning("tool_value_error tool=%s err=%s", func.__name__, exc)
            return error_response(f"Could not process the request: {exc}", ["Re-check the arguments and retry."])

    return wrapper
