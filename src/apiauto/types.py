"""Typed shapes of the apiauto.space API responses.

Every response is a plain ``dict`` (or a ``list`` of them); these ``TypedDict``
classes only describe the keys for type checkers and IDEs.

Prices and percentages are decimal strings such as ``"23900000.00"``, kept as
the API sends them so no precision is lost. Convert them when you need numbers::

    from decimal import Decimal

    amount = Decimal(car["price"]["amount"])

Times are ISO 8601 strings in UTC. A value the source does not provide is ``None``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, TypedDict

MarketCode = Literal["kr", "cn", "us"]
"""``kr`` is Encar (South Korea), ``cn`` is Che168 (China), ``us`` is Copart and IAAI."""

Sort = Literal["-first_seen", "first_seen", "price", "-price", "year", "-year", "mileage", "-mileage"]
"""Order of :meth:`apiauto.Client.cars`; ``-first_seen`` (newest first) by default."""

ChangeType = Literal["added", "disappeared", "price_drop", "price_up"]
"""Event types of the change feed."""

Dictionaries = dict[str, dict[str, list[str]]]
"""Field name -> canonical value -> synonyms, from :meth:`apiauto.Client.dictionaries`."""


class Price(TypedDict):
    """A price in the market's currency."""

    amount: str | None
    """Decimal string, for example ``"23900000.00"``."""
    currency: str
    """``KRW``, ``CNY`` or ``USD``."""


class Location(TypedDict):
    """Where the car is."""

    country: str
    """ISO 3166 code: ``KR``, ``CN`` or ``US``."""
    region: str | None
    """Province or US state."""
    city: str | None


class _CarRequired(TypedDict):
    id: str
    market: MarketCode
    source: Literal["encar", "che168", "copart", "iaai"]
    source_id: str
    title: str
    brand: str | None
    model: str | None
    generation: str | None
    trim: str | None
    year: int | None
    mileage_km: int | None
    fuel: str | None
    transmission: str | None
    engine_cc: int | None
    body_type: str | None
    color: str | None
    vin: str | None
    price: Price
    price_usd: str | None
    location: Location
    photos: list[str]
    photo_count: int
    listing_url: str | None
    is_active: bool
    first_seen_at: str
    last_seen_at: str
    disappeared_at: str | None
    updated_at: str
    source_mode: Literal["replica", "live"]
    raw: dict[str, Any]


class Car(_CarRequired, total=False):
    """One car record, the same keys in every market.

    ``id`` is ``source:source_id`` (``encar:43020893``) and never changes.
    ``photos`` are signed links that work for about a day: store the ``id``,
    not the links, and fetch a fresh record when you need the photos again.
    ``raw`` holds the fields only the source has, as the source sends them.
    """

    photos_more: int
    """How many more photos the record has beyond those in ``photos``."""
    raw_total: int
    """How many keys ``raw`` has in full."""


class CarsPage(TypedDict):
    """A page of :meth:`apiauto.Client.cars`."""

    items: list[Car]
    next_cursor: str | None
    """Pass it as ``cursor`` for the next page; ``None`` on the last one."""
    count: int | None
    """Cars matching the filters when there are at most 10,000; ``None`` above that."""


class Change(TypedDict):
    """One event of the change feed."""

    id: int
    car_id: str
    market: MarketCode
    type: ChangeType
    at: str
    old_price: str | None
    """Price before, a decimal string in the market's currency; price events only."""
    new_price: str | None
    """Price after, a decimal string in the market's currency; price events only."""
    pct: str | None
    """Size of the price change in percent, always positive; the direction is in ``type``."""


class ChangesPage(TypedDict):
    """A page of :meth:`apiauto.Client.changes`."""

    items: list[Change]
    next_cursor: str | None


class ReferenceItem(TypedDict):
    """A make or model as the catalog spells it, with the number of active cars."""

    name: str
    count: int


class Market(TypedDict):
    """Plan access and data freshness of one market."""

    market: MarketCode
    source: str
    available_in_plan: bool
    status: str
    data_updated_at: str | None
    data_age_seconds: int | None
    stale_after_seconds: int
    stale: bool
    active_cars: int


class UsageMarket(TypedDict):
    """Usage of one market in the current period."""

    market: MarketCode
    records: int
    requests: int
    live_us_requests: int


class Usage(TypedDict):
    """The plan, its term and how much of the quota is spent."""

    plan: str
    status: Literal["demo", "active", "grace"]
    expires_at: str
    period: str
    """``YYYY-MM``, or ``demo`` for the whole demo term."""
    reset_at: str
    quota_unit: Literal["records", "requests"]
    """Paid plans count returned records; the demo counts data requests."""
    quota_limit: int
    quota_used: int
    records_limit: int
    records_used: int
    live_us_limit: int
    live_us_used: int
    by_market: list[UsageMarket]


class CarFilters(TypedDict, total=False):
    """Optional filters of :meth:`apiauto.Client.cars` and :meth:`apiauto.Client.iter_cars`."""

    brand: str
    """A make as :meth:`apiauto.Client.brands` spells it; case, spaces and hyphens are ignored."""
    model: str
    """The model family, one name in every market: ``Grandeur``, ``3 Series``."""
    generation: str
    """Korea only: the generation as in the record's ``generation`` field."""
    trim: str
    """The trim, an exact match."""
    year_min: int
    year_max: int
    price_min: float | Decimal
    """Price from, in the market's currency (KRW, CNY or USD)."""
    price_max: float | Decimal
    """Price up to, in the market's currency."""
    price_usd_min: float | Decimal
    price_usd_max: float | Decimal
    mileage_max: int
    """Kilometres."""
    fuel: str
    """A canonical value from :meth:`apiauto.Client.dictionaries`."""
    transmission: str
    body_type: str
    has_photos: bool
    is_active: bool
    """``True`` by default; ``False`` returns cars taken off sale in the last 14 days."""
    q: str
    """Up to 6 words of the title: year, make, model, trim."""
    sort: Sort
    limit: int
    """Cars per page, 1-100 (up to 20 on the demo); 20 by default."""
    cursor: str
    """``next_cursor`` of the previous page."""
