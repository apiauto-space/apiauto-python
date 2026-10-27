"""The synchronous client."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from decimal import Decimal
from types import TracebackType
from typing import TYPE_CHECKING, Any, cast

import httpx

from ._base import (
    DEFAULT_BASE_URL,
    BaseClient,
    Pager,
    Params,
    build_params,
    car_path,
    cars_params,
    changes_params,
    check_market,
    connection_error,
)
from .errors import ApiautoError
from .types import (
    Car,
    CarsPage,
    Change,
    ChangesPage,
    ChangeType,
    Dictionaries,
    Market,
    MarketCode,
    ReferenceItem,
    Usage,
)

if TYPE_CHECKING:
    from typing_extensions import Self, Unpack

    from .types import CarFilters


class Client(BaseClient):
    """Synchronous client of the apiauto.space API.

    Args:
        api_key: Your key; defaults to the ``APIAUTO_KEY`` environment variable.
        base_url: The API root, ``https://api.apiauto.space/v1`` by default.
        timeout: Seconds to wait for a response. Ignored when ``http_client`` is given:
            configure the timeout on that client instead.
        max_retries: How many times to retry a request after 429, 5xx or a network
            error. 429 and 503 wait ``Retry-After`` (at most 60 s), the rest back off
            exponentially. Other 4xx errors are never retried.
        http_client: Your own ``httpx.Client`` (proxies, transports, event hooks).
            The client does not close it.

    Use it as a context manager or call :meth:`close` when done::

        with apiauto.Client() as client:
            page = client.cars("kr", brand="Kia", limit=20)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(api_key, base_url=base_url, max_retries=max_retries)
        self._owns_http = http_client is None
        self._http = http_client if http_client is not None else httpx.Client(timeout=timeout)
        self._sleep: Callable[[float], None] = time.sleep

    def close(self) -> None:
        """Close the underlying HTTP connections (unless the ``http_client`` was yours)."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _send(self, path: str, params: Params | None) -> httpx.Response:
        try:
            return self._http.get(self._url(path), params=params, headers=self._headers)
        except httpx.TransportError as exc:
            raise connection_error(exc) from exc

    def _get(self, path: str, params: Params | None = None) -> Any:
        attempt = 0
        while True:
            try:
                return self._parse(self._send(path, params))
            except ApiautoError as error:
                delay = self._retry_delay(error, attempt)
                if delay is None:
                    raise
                self._sleep(delay)
                attempt += 1

    def _paginate(self, path: str, params: Params, max_items: int | None) -> Iterator[Any]:
        pager = Pager(params, max_items)
        while (page_params := pager.next_params()) is not None:
            yield from pager.take(self._get(path, page_params))

    def cars(self, market: MarketCode, **filters: Unpack[CarFilters]) -> CarsPage:
        """Search one market's catalog: ``GET /cars``.

        Args:
            market: ``kr`` (Encar), ``cn`` (Che168) or ``us`` (Copart and IAAI).
            **filters: ``brand``, ``model``, ``generation``, ``trim``, ``year_min``,
                ``year_max``, ``price_min``, ``price_max``, ``price_usd_min``,
                ``price_usd_max``, ``mileage_max``, ``fuel``, ``transmission``,
                ``body_type``, ``has_photos``, ``is_active``, ``q``, ``sort``,
                ``limit`` and ``cursor``; see :class:`~apiauto.types.CarFilters`.

        Returns:
            A page: ``items``, ``next_cursor`` and ``count``. Every car returned
            counts against the quota.
        """
        return cast(CarsPage, self._get("/cars", cars_params(market, filters)))

    def iter_cars(
        self,
        market: MarketCode,
        *,
        max_items: int | None = None,
        **filters: Unpack[CarFilters],
    ) -> Iterator[Car]:
        """Iterate over every car matching the filters, following ``next_cursor``.

        Args:
            market: ``kr``, ``cn`` or ``us``.
            max_items: Stop after this many cars. The last request asks only for
                what is still needed, so no quota is spent on extra records.
            **filters: The filters of :meth:`cars`; ``limit`` sets the page size
                (pass ``limit=100`` on paid plans to make fewer requests).
        """
        return self._paginate("/cars", cars_params(market, filters), max_items)

    def car(self, car_id: str) -> Car:
        """Fetch one car by its id, such as ``encar:43020893``: ``GET /cars/{id}``.

        Cars taken off sale stay available for 14 days with ``is_active=False``.
        """
        return cast(Car, self._get(car_path(car_id)))

    def changes(
        self,
        market: MarketCode,
        since: datetime | str,
        *,
        type: ChangeType | Sequence[ChangeType] | None = None,  # noqa: A002
        min_pct: float | Decimal | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ChangesPage:
        """Read the change feed: ``GET /changes``.

        Args:
            market: ``kr``, ``cn`` or ``us``.
            since: Events after this moment: a ``datetime`` (naive means UTC) or
                an ISO 8601 string with a time zone.
            type: ``added``, ``disappeared``, ``price_drop``, ``price_up`` or a list
                of them; every type when omitted.
            min_pct: Smallest price change in percent (0.5 by default on the server).
            limit: Events per page, 1-100.
            cursor: ``next_cursor`` of the previous page.

        Each event counts as one record. The feed comes with the Pro, Max and demo plans.
        """
        params = changes_params(market, since, type, min_pct, limit, cursor)
        return cast(ChangesPage, self._get("/changes", params))

    def iter_changes(
        self,
        market: MarketCode,
        since: datetime | str,
        *,
        type: ChangeType | Sequence[ChangeType] | None = None,  # noqa: A002
        min_pct: float | Decimal | None = None,
        limit: int | None = None,
        max_items: int | None = None,
    ) -> Iterator[Change]:
        """Iterate over every event since a moment, following ``next_cursor``.

        Takes the arguments of :meth:`changes` plus ``max_items``.
        """
        params = changes_params(market, since, type, min_pct, limit, None)
        return self._paginate("/changes", params, max_items)

    def brands(self, market: MarketCode) -> list[ReferenceItem]:
        """A market's makes with car counts, most frequent first. Free."""
        params = build_params(market=check_market(market))
        return cast(list[ReferenceItem], self._get("/references/brands", params))

    def models(self, market: MarketCode, brand: str) -> list[ReferenceItem]:
        """A make's models with car counts. Free."""
        params = build_params(market=check_market(market), brand=brand)
        return cast(list[ReferenceItem], self._get("/references/models", params))

    def dictionaries(self) -> Dictionaries:
        """Canonical values of ``fuel``, ``transmission``, ``body_type`` and more, with synonyms. Free."""
        return cast(Dictionaries, self._get("/references/dictionaries"))

    def markets(self) -> list[Market]:
        """Every market: plan access, status, data age and the number of active cars. Free."""
        return cast(list[Market], self._get("/references/markets")["items"])

    def usage(self) -> Usage:
        """The plan, its term and how much of the quota is spent. Free."""
        return cast(Usage, self._get("/usage"))

    def us_live(
        self,
        *,
        make: str | None = None,
        model: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        price_max: int | None = None,
        page: int | None = None,
    ) -> list[Car]:
        """Search Copart and IAAI lots live at the auction data provider: ``GET /us/live``.

        For cars that are not in the catalog copy yet. Pro and Max plans; it spends a
        separate monthly counter, not the car quota. ``price_max`` is in US dollars,
        ``page`` is 1-100.
        """
        params = build_params(
            make=make, model=model, year_min=year_min, year_max=year_max, price_max=price_max, page=page
        )
        return cast(list[Car], self._get("/us/live", params))
