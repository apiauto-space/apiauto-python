from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
import pytest

import apiauto
from apiauto._base import USER_AGENT
from conftest import KEY, Recorder, car, cars_page

MakeClient = Callable[..., apiauto.Client]


def ok(body: Any, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(200, json=body, headers=headers)


# --- requests ---------------------------------------------------------------


def test_cars_sends_key_user_agent_and_filters(make_client: MakeClient) -> None:
    recorder = Recorder(ok(cars_page(["encar:1"], None)))
    client = make_client(recorder)

    page = client.cars(
        "kr",
        brand="Kia",
        year_min=2020,
        price_max=Decimal("25000000.50"),
        price_usd_max=18000.5,
        has_photos=True,
        is_active=False,
        sort="-price",
        limit=20,
    )

    assert page["items"][0]["id"] == "encar:1"
    request = recorder.last
    assert request.url.path == "/v1/cars"
    assert request.headers["X-API-Key"] == KEY
    assert request.headers["User-Agent"] == USER_AGENT
    assert USER_AGENT.startswith(f"apiauto-python/{apiauto.__version__} ")
    assert dict(request.url.params) == {
        "market": "kr",
        "brand": "Kia",
        "year_min": "2020",
        "price_max": "25000000.50",
        "price_usd_max": "18000.5",
        "has_photos": "true",
        "is_active": "false",
        "sort": "-price",
        "limit": "20",
    }


def test_unknown_filter_is_rejected_before_any_request(make_client: MakeClient) -> None:
    recorder = Recorder()
    client = make_client(recorder)
    with pytest.raises(TypeError, match="year_from"):
        client.cars("kr", year_from=2020)  # type: ignore[call-arg]
    assert recorder.requests == []


def test_unknown_market_is_rejected(make_client: MakeClient) -> None:
    client = make_client(Recorder())
    with pytest.raises(ValueError, match="market"):
        client.cars("jp")  # type: ignore[arg-type]


def test_car_path_keeps_the_colon(make_client: MakeClient) -> None:
    recorder = Recorder(ok(car("che168:59997083")))
    client = make_client(recorder)
    assert client.car("che168:59997083")["id"] == "che168:59997083"
    assert recorder.last.url.raw_path == b"/v1/cars/che168:59997083"


@pytest.mark.parametrize(
    ("since", "expected"),
    [
        (datetime(2026, 10, 27, 9, 30), "2026-10-27T09:30:00Z"),
        (datetime(2026, 10, 27, 12, 30, tzinfo=timezone(timedelta(hours=3))), "2026-10-27T09:30:00Z"),
        ("2026-10-27T00:00:00+09:00", "2026-10-27T00:00:00+09:00"),
    ],
)
def test_changes_serializes_since(make_client: MakeClient, since: datetime | str, expected: str) -> None:
    recorder = Recorder(ok({"items": [], "next_cursor": None}))
    make_client(recorder).changes("kr", since)
    assert recorder.last.url.params["since"] == expected


def test_changes_repeats_type_and_drops_none(make_client: MakeClient) -> None:
    recorder = Recorder(ok({"items": [], "next_cursor": None}))
    make_client(recorder).changes(
        "cn", "2026-10-27T00:00:00Z", type=["price_drop", "price_up"], min_pct=Decimal("5")
    )
    params = recorder.last.url.params
    assert params.get_list("type") == ["price_drop", "price_up"]
    assert params["min_pct"] == "5"
    assert "limit" not in params
    assert "cursor" not in params


def test_changes_accepts_a_single_type(make_client: MakeClient) -> None:
    recorder = Recorder(ok({"items": [], "next_cursor": None}))
    make_client(recorder).changes("us", "2026-10-27T00:00:00Z", type="added")
    assert recorder.last.url.params.get_list("type") == ["added"]


def test_references_usage_and_live(make_client: MakeClient) -> None:
    brands = [{"name": "Kia", "count": 3}]
    markets = {"items": [{"market": "kr", "source": "encar", "stale": False}]}
    dictionaries = {"fuel": {"diesel": ["diesel", "dizel"]}}
    usage = {"plan": "demo", "quota_used": 3}
    recorder = Recorder(ok(brands), ok(brands), ok(dictionaries), ok(markets), ok(usage), ok([car()]))
    client = make_client(recorder)

    assert client.brands("kr") == brands
    assert dict(recorder.last.url.params) == {"market": "kr"}
    assert client.models("kr", "Kia") == brands
    assert dict(recorder.last.url.params) == {"market": "kr", "brand": "Kia"}
    assert client.dictionaries() == dictionaries
    assert client.markets() == markets["items"]
    assert client.usage() == usage
    assert client.us_live(make="Toyota", year_min=2020, page=2)[0]["id"] == "encar:43020893"
    assert recorder.last.url.path == "/v1/us/live"
    assert dict(recorder.last.url.params) == {"make": "Toyota", "year_min": "2020", "page": "2"}


# --- pagination -------------------------------------------------------------


def test_iter_cars_follows_the_cursor(make_client: MakeClient) -> None:
    recorder = Recorder(
        ok(cars_page(["encar:1", "encar:2"], "c1")),
        ok(cars_page(["encar:3"], "c2")),
        ok(cars_page(["encar:4"], None)),
    )
    ids = [c["id"] for c in make_client(recorder).iter_cars("kr", brand="Kia")]

    assert ids == ["encar:1", "encar:2", "encar:3", "encar:4"]
    cursors = [r.url.params.get("cursor") for r in recorder.requests]
    assert cursors == [None, "c1", "c2"]
    assert all(r.url.params["brand"] == "Kia" for r in recorder.requests)


def test_iter_cars_max_items_stops_and_shrinks_the_last_page(make_client: MakeClient) -> None:
    recorder = Recorder(
        ok(cars_page(["encar:1", "encar:2", "encar:3"], "c1")),
        ok(cars_page(["encar:4", "encar:5"], "c2")),
    )
    ids = [c["id"] for c in make_client(recorder).iter_cars("kr", max_items=5, limit=3)]

    assert ids == ["encar:1", "encar:2", "encar:3", "encar:4", "encar:5"]
    assert [r.url.params["limit"] for r in recorder.requests] == ["3", "2"]


def test_iter_cars_max_items_uses_the_default_page_size(make_client: MakeClient) -> None:
    recorder = Recorder(ok(cars_page(["encar:1", "encar:2"], "c1")))
    ids = [c["id"] for c in make_client(recorder).iter_cars("kr", max_items=2)]
    assert ids == ["encar:1", "encar:2"]
    assert recorder.last.url.params["limit"] == "2"


def test_iter_stops_on_an_empty_page_even_with_a_cursor(make_client: MakeClient) -> None:
    recorder = Recorder(ok(cars_page([], "c1")))
    assert list(make_client(recorder).iter_cars("cn")) == []
    assert len(recorder.requests) == 1


def test_iter_with_max_items_zero_sends_nothing(make_client: MakeClient) -> None:
    recorder = Recorder()
    assert list(make_client(recorder).iter_cars("cn", max_items=0)) == []
    assert recorder.requests == []


def test_iter_changes(make_client: MakeClient) -> None:
    event = {"id": 1, "car_id": "encar:1", "type": "added"}
    recorder = Recorder(
        ok({"items": [event], "next_cursor": "c1"}),
        ok({"items": [{**event, "id": 2}], "next_cursor": None}),
    )
    events = list(make_client(recorder).iter_changes("kr", "2026-10-27T00:00:00Z", limit=1))
    assert [e["id"] for e in events] == [1, 2]
    assert recorder.requests[1].url.params["cursor"] == "c1"
    assert recorder.requests[1].url.params["since"] == "2026-10-27T00:00:00Z"


# --- errors -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "body", "error_class"),
    [
        (400, {"error": "bad_request", "detail": "offset is not supported"}, apiauto.BadRequestError),
        (401, {"error": "unauthorized"}, apiauto.AuthenticationError),
        (402, {"error": "quota_exhausted", "reset_at": "2026-11-01T00:00:00Z"}, apiauto.QuotaExceededError),
        (403, {"error": "market_not_in_plan", "markets": ["kr"]}, apiauto.PermissionDeniedError),
        (404, {"error": "not_found"}, apiauto.NotFoundError),
        (429, {"error": "rate_limited", "retry_after": 1}, apiauto.RateLimitError),
        (500, {"error": "internal_error"}, apiauto.ServerError),
        (502, {"error": "image_upstream_unavailable"}, apiauto.ServerError),
        (503, {"error": "upstream_unavailable", "retry_after": 30}, apiauto.ServiceUnavailableError),
        (405, {"error": "method_not_allowed"}, apiauto.ApiautoError),
    ],
)
def test_error_mapping(
    make_client: MakeClient, status: int, body: dict[str, Any], error_class: type[apiauto.ApiautoError]
) -> None:
    client = make_client(Recorder(httpx.Response(status, json=body)), max_retries=0)

    with pytest.raises(error_class) as caught:
        client.usage()

    error = caught.value
    assert type(error) is error_class
    assert error.status_code == status
    assert error.code == body["error"]
    assert error.detail == body.get("detail")
    assert error.reset_at == body.get("reset_at")
    assert error.retry_after == body.get("retry_after")
    assert error.body == body
    assert str(error).startswith(f"HTTP {status} {body['error']}")
    assert client.last_response is not None
    assert client.last_response.status == status


def test_service_unavailable_is_a_server_error() -> None:
    assert issubclass(apiauto.ServiceUnavailableError, apiauto.ServerError)


def test_error_detail_is_in_the_message(make_client: MakeClient) -> None:
    body = {"error": "bad_request", "detail": "limit above the plan"}
    client = make_client(Recorder(httpx.Response(400, json=body)))
    with pytest.raises(apiauto.BadRequestError, match="HTTP 400 bad_request: limit above the plan"):
        client.cars("kr", limit=100)


def test_non_json_error_body(make_client: MakeClient) -> None:
    response = httpx.Response(502, text="<html>Bad Gateway</html>", headers={"Content-Type": "text/html"})
    client = make_client(Recorder(response), max_retries=0)

    with pytest.raises(apiauto.ServerError) as caught:
        client.usage()

    assert caught.value.code is None
    assert caught.value.body == "<html>Bad Gateway</html>"
    assert "Bad Gateway" in str(caught.value)


def test_non_json_success_body(make_client: MakeClient) -> None:
    client = make_client(Recorder(httpx.Response(200, text="not json")))
    with pytest.raises(apiauto.ApiautoError, match="not JSON"):
        client.usage()


# --- retries ----------------------------------------------------------------


def test_retries_429_after_retry_after_header(make_client: MakeClient, sleeps: list[float]) -> None:
    recorder = Recorder(
        httpx.Response(429, json={"error": "rate_limited"}, headers={"Retry-After": "3"}),
        ok({"plan": "demo"}),
    )
    assert make_client(recorder).usage()["plan"] == "demo"
    assert sleeps == [3.0]
    assert len(recorder.requests) == 2


def test_retry_after_from_body_is_capped(make_client: MakeClient, sleeps: list[float]) -> None:
    recorder = Recorder(
        httpx.Response(503, json={"error": "upstream_unavailable", "retry_after": 600}),
        ok([]),
    )
    assert make_client(recorder).us_live(make="Toyota") == []
    assert sleeps == [60.0]


def test_server_errors_back_off_then_give_up(make_client: MakeClient, sleeps: list[float]) -> None:
    recorder = Recorder(*(httpx.Response(500, json={"error": "internal_error"}) for _ in range(3)))
    with pytest.raises(apiauto.ServerError):
        make_client(recorder, max_retries=2).usage()
    assert len(recorder.requests) == 3
    assert len(sleeps) == 2
    assert 0.25 <= sleeps[0] <= 0.5
    assert 0.5 <= sleeps[1] <= 1.0


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
def test_client_errors_are_not_retried(make_client: MakeClient, sleeps: list[float], status: int) -> None:
    recorder = Recorder(httpx.Response(status, json={"error": "x"}), ok({}))
    with pytest.raises(apiauto.ApiautoError):
        make_client(recorder).usage()
    assert len(recorder.requests) == 1
    assert sleeps == []


def test_connection_errors_are_retried_then_raised(make_client: MakeClient, sleeps: list[float]) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(apiauto.APIConnectionError, match="timed out") as caught:
        make_client(handler, max_retries=1).usage()
    assert isinstance(caught.value.__cause__, httpx.ConnectTimeout)
    assert caught.value.status_code is None
    assert calls == 2
    assert len(sleeps) == 1


def test_max_retries_zero_disables_retries(make_client: MakeClient, sleeps: list[float]) -> None:
    recorder = Recorder(httpx.Response(429, json={"error": "rate_limited", "retry_after": 1}))
    with pytest.raises(apiauto.RateLimitError) as caught:
        make_client(recorder, max_retries=0).usage()
    assert caught.value.retry_after == 1
    assert sleeps == []


# --- configuration and metadata --------------------------------------------


def test_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIAUTO_KEY", " env-key \n")
    recorder = Recorder(ok({}))
    with apiauto.Client(http_client=httpx.Client(transport=httpx.MockTransport(recorder))) as client:
        client.usage()
    assert recorder.last.headers["X-API-Key"] == "env-key"


def test_explicit_key_wins_over_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIAUTO_KEY", "env-key")
    recorder = Recorder(ok({}))
    with apiauto.Client("explicit", http_client=httpx.Client(transport=httpx.MockTransport(recorder))) as c:
        c.usage()
    assert recorder.last.headers["X-API-Key"] == "explicit"


def test_missing_key_is_a_clear_error() -> None:
    with pytest.raises(apiauto.ApiautoError, match="APIAUTO_KEY"):
        apiauto.Client()
    with pytest.raises(apiauto.ApiautoError, match="APIAUTO_KEY"):
        apiauto.AsyncClient("  ")


def test_repr_masks_the_key(make_client: MakeClient) -> None:
    client = make_client(Recorder())
    assert KEY not in repr(client)
    assert repr(client) == "Client(base_url='https://api.apiauto.space/v1', api_key='***')"


def test_base_url_is_configurable(make_client: MakeClient) -> None:
    recorder = Recorder(ok({}))
    make_client(recorder, base_url="http://localhost:8000/v1/").usage()
    assert str(recorder.last.url) == "http://localhost:8000/v1/usage"


def test_last_response_reads_quota_headers(make_client: MakeClient) -> None:
    headers = {
        "X-Quota-Limit": "2000000",
        "X-Quota-Remaining": "1786983",
        "X-Quota-Reset": "2026-11-01T00:00:00Z",
        "X-RateLimit-Limit": "10",
        "X-RateLimit-Remaining": "9",
        "X-RateLimit-Reset": "1",
        "X-Data-Age-Seconds": "2361",
    }
    client = make_client(Recorder(ok(cars_page([], None), headers)))
    assert client.last_response is None
    client.cars("cn", limit=1)
    assert client.last_response == apiauto.ResponseInfo(
        status=200,
        quota_limit=2_000_000,
        quota_remaining=1_786_983,
        quota_reset="2026-11-01T00:00:00Z",
        rate_limit=10,
        rate_remaining=9,
        rate_reset=1,
        data_age_seconds=2361,
    )


def test_missing_or_bad_headers_are_none(make_client: MakeClient) -> None:
    client = make_client(Recorder(ok({}, {"X-Quota-Remaining": "lots"})))
    client.usage()
    assert client.last_response == apiauto.ResponseInfo(status=200)


def test_close_leaves_a_borrowed_http_client_open() -> None:
    http = httpx.Client(transport=httpx.MockTransport(Recorder()))
    with apiauto.Client(KEY, http_client=http):
        pass
    assert not http.is_closed
    http.close()


def test_close_closes_an_owned_http_client() -> None:
    client = apiauto.Client(KEY)
    client.close()
    assert client._http.is_closed
