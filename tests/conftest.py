from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

import apiauto

KEY = "test-key-1234567890"

Handler = Callable[[httpx.Request], httpx.Response]


def car(car_id: str = "encar:43020893") -> dict[str, Any]:
    """A shortened record, enough for the client (it does not validate records)."""
    return {"id": car_id, "market": "kr", "title": "2020 Kia Mohave", "price": {"amount": "1.00"}}


def cars_page(ids: list[str], next_cursor: str | None) -> dict[str, Any]:
    return {"items": [car(i) for i in ids], "next_cursor": next_cursor, "count": None}


class Recorder:
    """A MockTransport handler that replays queued responses and records requests."""

    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never see a real key from the environment."""
    monkeypatch.delenv("APIAUTO_KEY", raising=False)


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def make_client(sleeps: list[float]) -> Iterator[Callable[..., apiauto.Client]]:
    clients: list[apiauto.Client] = []

    def factory(handler: Handler, **kwargs: Any) -> apiauto.Client:
        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = apiauto.Client(KEY, http_client=http, **kwargs)
        client._sleep = sleeps.append
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def make_async_client(sleeps: list[float]) -> Callable[..., apiauto.AsyncClient]:
    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def factory(handler: Handler, **kwargs: Any) -> apiauto.AsyncClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = apiauto.AsyncClient(KEY, http_client=http, **kwargs)
        client._sleep = fake_sleep
        return client

    return factory
