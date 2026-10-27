"""Exceptions raised by the apiauto client.

Every API error is JSON like ``{"error": "quota_exhausted", "reset_at": "..."}``;
the client turns it into a subclass of :class:`ApiautoError` chosen by the
HTTP status, with the body's fields as attributes.
"""

from __future__ import annotations

from typing import Any


class ApiautoError(Exception):
    """Base class of every error the client raises.

    Attributes:
        message: A human-readable summary.
        status_code: The HTTP status, or ``None`` when no response came.
        code: The ``error`` field of the body, such as ``quota_exhausted``.
        detail: The ``detail`` field: what exactly is wrong with the request.
        body: The parsed JSON body, or the raw text when the body is not JSON.
        retry_after: Seconds to wait before retrying (429 and 503).
        reset_at: When the quota renews, ISO 8601 (402).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        detail: str | None = None,
        body: Any = None,
        retry_after: int | None = None,
        reset_at: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.body = body
        self.retry_after = retry_after
        self.reset_at = reset_at


class APIConnectionError(ApiautoError):
    """The request did not get a response: network failure or timeout."""


class BadRequestError(ApiautoError):
    """400: a bad parameter, a ``limit`` above the plan's, or ``offset`` given."""


class AuthenticationError(ApiautoError):
    """401: no key, a wrong or revoked key, or the subscription has ended."""


class QuotaExceededError(ApiautoError):
    """402: the period quota is spent; ``reset_at`` says when it renews."""


class PermissionDeniedError(ApiautoError):
    """403: the market or feature is not in the plan (``body["markets"]`` lists the plan's markets)."""


class NotFoundError(ApiautoError):
    """404: no such car or path."""


class RateLimitError(ApiautoError):
    """429: more requests per second than the plan allows; see ``retry_after``."""


class ServerError(ApiautoError):
    """5xx: a server-side failure."""


class ServiceUnavailableError(ServerError):
    """503: the upstream provider of live US search is unavailable; see ``retry_after``."""


STATUS_ERRORS: dict[int, type[ApiautoError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: QuotaExceededError,
    403: PermissionDeniedError,
    404: NotFoundError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}
