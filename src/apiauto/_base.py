"""Request building, response parsing and retry rules shared by both clients."""

from __future__ import annotations

import os
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from ._version import __version__
from .errors import (
    STATUS_ERRORS,
    ApiautoError,
    APIConnectionError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
)
from .types import CarFilters, ChangeType

DEFAULT_BASE_URL = "https://api.apiauto.space/v1"
API_KEY_ENV = "APIAUTO_KEY"
USER_AGENT = f"apiauto-python/{__version__} (+https://github.com/apiauto-space/apiauto-python)"
DEMO_KEY_URL = "https://t.me/apiautospace_bot?start=demo"

MARKETS = ("kr", "cn", "us")
DEFAULT_PAGE_SIZE = 20
MAX_RETRY_AFTER = 60.0
MAX_BACKOFF = 8.0

Params = dict[str, str | list[str]]

_CAR_FILTERS = frozenset(CarFilters.__annotations__)


@dataclass(frozen=True)
class ResponseInfo:
    """Quota and rate-limit headers of the last response.

    A header the response did not carry is ``None``: references and usage
    answers, for example, have no quota headers.
    """

    status: int
    quota_limit: int | None = None
    """The period quota (``X-Quota-Limit``)."""
    quota_remaining: int | None = None
    """What is left of the quota (``X-Quota-Remaining``)."""
    quota_reset: str | None = None
    """When the quota renews, ISO 8601 (``X-Quota-Reset``)."""
    rate_limit: int | None = None
    """Requests per second the plan allows (``X-RateLimit-Limit``)."""
    rate_remaining: int | None = None
    """Requests left in the current second (``X-RateLimit-Remaining``)."""
    rate_reset: int | None = None
    """Seconds until the rate window resets (``X-RateLimit-Reset``)."""
    data_age_seconds: int | None = None
    """Age of the market copy that answered (``X-Data-Age-Seconds``)."""

    @classmethod
    def from_response(cls, response: httpx.Response) -> ResponseInfo:
        """Read the metadata from a response's headers."""
        headers = response.headers
        return cls(
            status=response.status_code,
            quota_limit=_to_int(headers.get("X-Quota-Limit")),
            quota_remaining=_to_int(headers.get("X-Quota-Remaining")),
            quota_reset=headers.get("X-Quota-Reset"),
            rate_limit=_to_int(headers.get("X-RateLimit-Limit")),
            rate_remaining=_to_int(headers.get("X-RateLimit-Remaining")),
            rate_reset=_to_int(headers.get("X-RateLimit-Reset")),
            data_age_seconds=_to_int(headers.get("X-Data-Age-Seconds")),
        )


class BaseClient:
    """State and rules shared by :class:`~apiauto.Client` and :class:`~apiauto.AsyncClient`."""

    def __init__(self, api_key: str | None, *, base_url: str, max_retries: int) -> None:
        key = (api_key or os.environ.get(API_KEY_ENV) or "").strip()
        if not key:
            raise ApiautoError(
                f"No API key: pass api_key=... or set the {API_KEY_ENV} environment variable. "
                f"A free demo key comes from {DEMO_KEY_URL}"
            )
        if max_retries < 0:
            raise ValueError("max_retries must be 0 or more")
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "X-API-Key": key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        self.max_retries = max_retries
        self.last_response: ResponseInfo | None = None
        """Metadata of the last response, including error responses."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self._base_url!r}, api_key='***')"

    def _url(self, path: str) -> str:
        return self._base_url + path

    def _parse(self, response: httpx.Response) -> Any:
        """Return the JSON body of a successful response or raise the matching error."""
        self.last_response = ResponseInfo.from_response(response)
        if not response.is_success:
            raise error_from_response(response)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiautoError(
                "The API answered with a body that is not JSON",
                status_code=response.status_code,
                body=response.text,
            ) from exc

    def _retry_delay(self, error: ApiautoError, attempt: int) -> float | None:
        """Seconds to wait before retry number ``attempt + 1``, or ``None`` to give up."""
        if attempt >= self.max_retries:
            return None
        if isinstance(error, (RateLimitError, ServiceUnavailableError)) and error.retry_after is not None:
            return min(float(error.retry_after), MAX_RETRY_AFTER)
        if isinstance(error, (RateLimitError, ServerError, APIConnectionError)):
            return backoff(attempt)
        return None


class Pager:
    """Cursor-following state of one ``iter_*`` call, shared by the sync and async iterators."""

    def __init__(self, params: Params, max_items: int | None) -> None:
        self._params = params
        self._remaining = max_items
        self._done = max_items is not None and max_items <= 0

    def next_params(self) -> Params | None:
        """Query of the next request, or ``None`` when the iteration is over.

        With ``max_items`` the page size shrinks to what is still wanted, so the
        last page does not spend quota on records that would be thrown away.
        """
        if self._done:
            return None
        if self._remaining is None:
            return self._params
        page_size = int(str(self._params.get("limit", DEFAULT_PAGE_SIZE)))
        return {**self._params, "limit": str(min(page_size, self._remaining))}

    def take(self, page: Mapping[str, Any]) -> list[Any]:
        """Return the items of ``page`` to yield and move the cursor on."""
        items: list[Any] = page["items"]
        if self._remaining is not None:
            items = items[: self._remaining]
            self._remaining -= len(items)
        cursor = page.get("next_cursor")
        if not cursor or not items or self._remaining == 0:
            self._done = True
        else:
            self._params = {**self._params, "cursor": cursor}
        return items


def error_from_response(response: httpx.Response) -> ApiautoError:
    """Build the exception for an error response, tolerating bodies that are not JSON."""
    status = response.status_code
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    fields: Mapping[str, Any] = body if isinstance(body, dict) else {}
    code = _str_field(fields, "error")
    detail = _str_field(fields, "detail")
    reset_at = _str_field(fields, "reset_at")
    retry_after = _to_int(fields.get("retry_after"))
    if retry_after is None:
        retry_after = _to_int(response.headers.get("Retry-After"))

    message = f"HTTP {status}"
    if code:
        message += f" {code}"
    if detail:
        message += f": {detail}"
    elif not fields and isinstance(body, str) and body.strip():
        message += f": {body.strip()[:200]}"

    error_class = STATUS_ERRORS.get(status) or (ServerError if status >= 500 else ApiautoError)
    return error_class(
        message,
        status_code=status,
        code=code,
        detail=detail,
        body=body,
        retry_after=retry_after,
        reset_at=reset_at,
    )


def connection_error(exc: httpx.TransportError) -> APIConnectionError:
    """Wrap a network failure or timeout of httpx."""
    kind = "timed out" if isinstance(exc, httpx.TimeoutException) else "failed"
    return APIConnectionError(f"The request to the API {kind}: {exc}")


def backoff(attempt: int) -> float:
    """Exponential backoff with jitter: about 0.5 s, 1 s, 2 s ... up to 8 s."""
    return min(MAX_BACKOFF, 0.5 * 2.0**attempt) * random.uniform(0.5, 1.0)  # noqa: S311


def check_market(market: str) -> str:
    """Fail fast on a market code the API does not know."""
    if market not in MARKETS:
        raise ValueError(f"market must be one of {', '.join(MARKETS)}, got {market!r}")
    return market


def car_path(car_id: str) -> str:
    """Path of one car; the id is percent-encoded except for the ``:`` separator."""
    if not car_id:
        raise ValueError("car_id must not be empty")
    return "/cars/" + quote(car_id, safe=":")


def cars_params(market: str, filters: Mapping[str, Any]) -> Params:
    """Query of ``GET /cars``; rejects filter names the API does not have."""
    unknown = sorted(set(filters) - _CAR_FILTERS)
    if unknown:
        raise TypeError(f"Unknown car filter(s): {', '.join(unknown)}")
    return build_params(market=check_market(market), **filters)


def changes_params(
    market: str,
    since: datetime | str,
    type: ChangeType | Sequence[ChangeType] | None,  # noqa: A002
    min_pct: float | Decimal | None,
    limit: int | None,
    cursor: str | None,
) -> Params:
    """Query of ``GET /changes``; a single ``type`` or a list of them."""
    types = [type] if isinstance(type, str) else type
    return build_params(
        market=check_market(market),
        since=since,
        type=list(types) if types is not None else None,
        min_pct=min_pct,
        limit=limit,
        cursor=cursor,
    )


def build_params(**params: Any) -> Params:
    """Serialize query parameters.

    ``None`` values are dropped, booleans become ``true``/``false``, datetimes
    become ISO 8601 in UTC, lists and tuples become repeated parameters.
    """
    query: Params = {}
    for name, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            query[name] = [_to_query(item) for item in value]
        else:
            query[name] = _to_query(value)
    return query


def format_datetime(value: datetime) -> str:
    """ISO 8601 in UTC with a ``Z``; a naive datetime is taken to be UTC already."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_query(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return format_datetime(value)
    return str(value)


def _to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_field(fields: Mapping[str, Any], name: str) -> str | None:
    value = fields.get(name)
    return value if isinstance(value, str) else None
