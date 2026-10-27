"""Smoke test against the real API, skipped unless APIAUTO_KEY is set.

It spends at most 10 records of the quota (5 data requests on a demo key):
references and usage are free, the rest asks for 1-2 cars or events at a time.

    APIAUTO_KEY=... pytest tests/test_live.py
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import apiauto

# Read at import: the autouse fixture in conftest hides the variable from unit tests.
KEY = os.environ.get("APIAUTO_KEY", "").strip()

pytestmark = pytest.mark.skipif(not KEY, reason="set APIAUTO_KEY to run the live smoke test")


@pytest.fixture(scope="module")
def client() -> Iterator[apiauto.Client]:
    with apiauto.Client(KEY) as client:
        yield client


def test_free_endpoints(client: apiauto.Client) -> None:
    usage = client.usage()
    assert usage["quota_unit"] in ("records", "requests")

    markets = client.markets()
    assert {m["market"] for m in markets} == {"kr", "cn", "us"}

    brands = client.brands("kr")
    assert brands
    assert {"name", "count"} <= set(brands[0])

    assert "fuel" in client.dictionaries()


def test_cars_and_car_by_id(client: apiauto.Client) -> None:  # 3 records
    page = client.cars("cn", limit=2)
    assert 1 <= len(page["items"]) <= 2
    first = page["items"][0]
    assert first["market"] == "cn"
    assert first["id"].startswith("che168:")
    if first["price"]["amount"] is not None:
        assert Decimal(first["price"]["amount"]) >= 0

    info = client.last_response
    assert info is not None
    assert info.status == 200
    assert info.data_age_seconds is not None

    assert client.car(first["id"])["id"] == first["id"]


def test_iter_cars_respects_max_items(client: apiauto.Client) -> None:  # 3 records
    cars = list(client.iter_cars("kr", max_items=3, limit=2))
    assert len(cars) == 3
    assert len({c["id"] for c in cars}) == 3


def test_changes(client: apiauto.Client) -> None:  # up to 2 records
    since = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        page = client.changes("us", since, limit=2)
    except apiauto.PermissionDeniedError:
        pytest.skip("the change feed is not in this key's plan")
    assert len(page["items"]) <= 2


def test_unknown_car_is_not_found(client: apiauto.Client) -> None:
    with pytest.raises(apiauto.NotFoundError):
        client.car("encar:0")
