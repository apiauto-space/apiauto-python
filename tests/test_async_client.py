"""The async client shares request building and error mapping with the sync one;
these tests cover its own I/O path: awaiting, async iteration, retries and closing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any, TypeVar

import httpx
import pytest

import apiauto
from conftest import KEY, Recorder, car, cars_page

MakeAsyncClient = Callable[..., apiauto.AsyncClient]
T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def ok(body: Any) -> httpx.Response:
    return httpx.Response(200, json=body)


def test_cars_and_car(make_async_client: MakeAsyncClient) -> None:
    recorder = Recorder(ok(cars_page(["encar:1"], None)), ok(car("encar:1")))

    async def main() -> None:
        async with make_async_client(recorder) as client:
            page = await client.cars("kr", brand="Kia", has_photos=False)
            assert page["items"][0]["id"] == "encar:1"
            assert (await client.car("encar:1"))["id"] == "encar:1"

    run(main())
    first = recorder.requests[0]
    assert first.headers["X-API-Key"] == KEY
    assert dict(first.url.params) == {"market": "kr", "brand": "Kia", "has_photos": "false"}
    assert recorder.last.url.path == "/v1/cars/encar:1"


def test_iter_cars_with_max_items(make_async_client: MakeAsyncClient) -> None:
    recorder = Recorder(
        ok(cars_page(["cn:1", "cn:2"], "c1")),
        ok(cars_page(["cn:3"], "c2")),
    )

    async def main() -> list[str]:
        async with make_async_client(recorder) as client:
            return [c["id"] async for c in client.iter_cars("cn", max_items=3, limit=2)]

    assert run(main()) == ["cn:1", "cn:2", "cn:3"]
    assert [r.url.params["limit"] for r in recorder.requests] == ["2", "1"]
    assert recorder.last.url.params["cursor"] == "c1"


def test_iter_changes(make_async_client: MakeAsyncClient) -> None:
    recorder = Recorder(
        ok({"items": [{"id": 1}], "next_cursor": "c1"}),
        ok({"items": [{"id": 2}], "next_cursor": None}),
    )

    async def main() -> list[int]:
        async with make_async_client(recorder) as client:
            since = datetime(2026, 10, 27)
            return [e["id"] async for e in client.iter_changes("us", since, type="price_drop")]

    assert run(main()) == [1, 2]
    assert recorder.last.url.params["since"] == "2026-10-27T00:00:00Z"
    assert recorder.last.url.params["type"] == "price_drop"


def test_references_and_usage(make_async_client: MakeAsyncClient) -> None:
    recorder = Recorder(ok([]), ok([]), ok({}), ok({"items": []}), ok({"plan": "max"}), ok([]))

    async def main() -> None:
        async with make_async_client(recorder) as client:
            assert await client.brands("us") == []
            assert await client.models("us", "Toyota") == []
            assert await client.dictionaries() == {}
            assert await client.markets() == []
            assert (await client.usage())["plan"] == "max"
            assert await client.us_live(model="Camry") == []

    run(main())
    assert [r.url.path for r in recorder.requests] == [
        "/v1/references/brands",
        "/v1/references/models",
        "/v1/references/dictionaries",
        "/v1/references/markets",
        "/v1/usage",
        "/v1/us/live",
    ]


def test_retries_429_then_succeeds(make_async_client: MakeAsyncClient, sleeps: list[float]) -> None:
    recorder = Recorder(
        httpx.Response(429, json={"error": "rate_limited", "retry_after": 2}),
        ok({"plan": "demo"}),
    )

    async def main() -> Any:
        async with make_async_client(recorder) as client:
            return await client.usage()

    assert run(main()) == {"plan": "demo"}
    assert sleeps == [2.0]


def test_401_is_not_retried(make_async_client: MakeAsyncClient, sleeps: list[float]) -> None:
    recorder = Recorder(httpx.Response(401, json={"error": "unauthorized"}), ok({}))

    async def main() -> None:
        async with make_async_client(recorder) as client:
            await client.usage()

    with pytest.raises(apiauto.AuthenticationError):
        run(main())
    assert len(recorder.requests) == 1
    assert sleeps == []


def test_connection_error(make_async_client: MakeAsyncClient, sleeps: list[float]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async def main() -> None:
        async with make_async_client(handler, max_retries=2) as client:
            await client.usage()

    with pytest.raises(apiauto.APIConnectionError, match="failed"):
        run(main())
    assert len(sleeps) == 2


def test_repr_masks_the_key(make_async_client: MakeAsyncClient) -> None:
    client = make_async_client(Recorder())
    assert KEY not in repr(client)
    assert repr(client).startswith("AsyncClient(")


def test_close_closes_an_owned_http_client() -> None:
    async def main() -> bool:
        client = apiauto.AsyncClient(KEY)
        await client.close()
        return client._http.is_closed

    assert run(main())
