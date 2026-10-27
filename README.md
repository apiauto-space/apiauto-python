# apiauto — Python client for the Encar, Che168, Copart and IAAI API

[![PyPI version](https://img.shields.io/pypi/v/apiauto-space.svg)](https://pypi.org/project/apiauto-space/)
[![Python versions](https://img.shields.io/pypi/pyversions/apiauto-space.svg)](https://pypi.org/project/apiauto-space/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/apiauto-space/apiauto-python/blob/main/LICENSE)

`apiauto` is a typed Python client for the [apiauto.space](https://apiauto.space/en/) REST API: used-car
listings from **Encar** (South Korea), **Che168** (China) and the **Copart** and **IAAI** auctions (USA) in
one JSON record format, without writing a scraper. Search the catalogs by make, model, year, price and
mileage, page through whole markets, follow a feed of new cars, sold cars and price changes, and read
quota headers — from sync or async code. It is an unofficial client: the project is not affiliated with
Encar, Che168/Autohome, Copart or IAAI; the data comes through the apiauto.space API.

- Sync `Client` and `AsyncClient` on top of [httpx](https://www.python-httpx.org/), the only dependency
- Iterators that follow the cursor for you, with `max_items` that never over-spends the quota
- Automatic retries on 429 and 503 (honouring `Retry-After`) and on 5xx and network errors
- One exception class per API error: `QuotaExceededError`, `RateLimitError`, `NotFoundError` ...
- `TypedDict` types for every response, `py.typed`, checked with `mypy --strict`
- Python 3.10+

## Install

```bash
pip install apiauto-space
```

The distribution is called `apiauto-space` on PyPI; the module you import is `apiauto`.

## Get a key

Open the Telegram bot [@apiautospace_bot](https://t.me/apiautospace_bot?start=demo) and take a free demo
key: one day, 100 data requests, up to 20 cars per request, all three markets. Paid plans are on the
[pricing page](https://apiauto.space/en/#pricing).

Save the key in the `APIAUTO_KEY` environment variable — the client reads it from there:

```bash
export APIAUTO_KEY="your-key"
```

Keep the key on your server. The API does not accept browser requests (CORS is off), and a key in page
code is visible to every visitor.

## Quick start

```python
import apiauto

client = apiauto.Client()  # reads APIAUTO_KEY

page = client.cars("kr", brand="Kia", model="Sorento", year_min=2021, limit=20)
for car in page["items"]:
    print(car["id"], car["title"], car["price"]["amount"], car["price"]["currency"])
```

Markets are `kr` (Encar, Korea), `cn` (Che168, China) and `us` (Copart and IAAI, USA). Every record has
the same keys in every market; a value the source does not provide is `None`.

## Examples

### Search Encar by make, model, year and price

```python
page = client.cars(
    "kr",
    brand="Hyundai",
    model="Grandeur",
    year_min=2020,
    year_max=2023,
    price_min=10_000_000,  # in the market's currency: KRW for Korea; skips monthly lease payments
    price_max=30_000_000,
    mileage_max=80_000,  # km
    sort="-first_seen",  # newest listings first (the default)
    limit=20,
)
print(page["count"], "cars match")  # None when more than 10,000 match
```

Prices in dollars at the ECB rate work in every market: `price_usd_min=15000, price_usd_max=25000`.
The full list of filters: `brand`, `model`, `generation` (Korea), `trim`, `year_min`, `year_max`,
`price_min`, `price_max`, `price_usd_min`, `price_usd_max`, `mileage_max`, `fuel`, `transmission`,
`body_type`, `has_photos`, `is_active`, `q` (words of the title), `sort`, `limit`, `cursor`.

### Search Che168 (China)

```python
for car in client.cars("cn", brand="BYD", fuel="electric", has_photos=True, limit=10)["items"]:
    print(car["title"], car["price"]["amount"], "CNY", car["location"]["city"])
```

### US auction lots: Copart and IAAI

```python
for lot in client.cars("us", brand="Toyota", model="Camry", year_min=2020, limit=10)["items"]:
    raw = lot["raw"]  # auction-only fields as the source sends them
    print(lot["id"], lot["vin"], lot["mileage_km"], raw.get("damage_main"), raw.get("sale_date"))
```

Cars that are not in the copy yet can be searched live at the auction data provider (Pro and Max plans,
a separate monthly counter): `client.us_live(make="Toyota", model="Camry", year_min=2020)`.

### Iterate over all pages

```python
for car in client.iter_cars("kr", brand="Genesis", limit=100, max_items=1000):
    save(car)
```

`iter_cars` follows `next_cursor` until the last page. With `max_items` the last request asks only for
the cars still needed, so the quota is not spent on records that would be thrown away. The demo allows
`limit` up to 20; paid plans up to 100.

### Get a car by id

```python
car = client.car("encar:43020893")
print(car["is_active"], car["listing_url"])
```

Ids look like `encar:…`, `che168:…`, `copart:…` and `iaai:…` and never change. A sold or removed car
stays available for 14 days with `is_active=False`.

### Keep a catalog in sync with the change feed

```python
import time
from datetime import datetime, timezone

since = datetime.now(timezone.utc)
while True:
    time.sleep(3600)  # the market copy is refreshed hourly
    polled_at = datetime.now(timezone.utc)
    for event in client.iter_changes("kr", since, limit=100):
        if event["type"] == "added":
            save(client.car(event["car_id"]))
        elif event["type"] == "disappeared":
            mark_sold(event["car_id"])
        else:  # price_drop or price_up
            update_price(event["car_id"], event["new_price"])
    since = polled_at
```

`since` takes a `datetime` (a naive one is treated as UTC) or an ISO 8601 string. Filter by
`type="price_drop"` (or a list of types) and `min_pct=5`. The feed comes with the Pro, Max and demo
plans; each event counts as one record. A complete script is in
[examples/sync_changes.py](https://github.com/apiauto-space/apiauto-python/blob/main/examples/sync_changes.py).

### References: makes, models, canonical values, freshness

These calls are free.

```python
client.brands("cn")  # [{"name": "Mercedes-Benz", "count": 20185}, ...]
client.models("kr", "Hyundai")  # the make's models with car counts
client.dictionaries()["fuel"]  # {"gasoline": ["gasoline", "petrol", ...], "diesel": [...], ...}
for market in client.markets():
    print(market["market"], market["active_cars"], market["data_age_seconds"], market["stale"])
```

### Usage and quota headers

The quota counts returned cars (records), not requests; the demo counts data requests.

```python
usage = client.usage()  # free
print(usage["plan"], usage["quota_used"], "/", usage["quota_limit"], usage["quota_unit"])

client.cars("us", limit=5)
info = client.last_response
print(info.quota_remaining, info.quota_reset, info.rate_remaining, info.data_age_seconds)
```

`client.last_response` is a frozen `ResponseInfo` read from the `X-Quota-*`, `X-RateLimit-*` and
`X-Data-Age-Seconds` headers of the last response; a header that was not sent is `None`.

### Async

```python
import asyncio
import apiauto


async def main() -> None:
    async with apiauto.AsyncClient() as client:
        page = await client.cars("cn", brand="Toyota", limit=10)
        async for car in client.iter_cars("kr", brand="Kia", max_items=50):
            print(car["title"])


asyncio.run(main())
```

`AsyncClient` has the same methods as `Client`; `iter_cars` and `iter_changes` return async iterators.

### Errors and retries

```python
try:
    car = client.car("encar:1")
except apiauto.NotFoundError:
    car = None
except apiauto.QuotaExceededError as error:
    print("quota renews at", error.reset_at)
except apiauto.ApiautoError as error:
    print(error.status_code, error.code, error.detail)
```

| HTTP | Exception | Retried |
| --- | --- | --- |
| 400 | `BadRequestError` | no |
| 401 | `AuthenticationError` | no |
| 402 | `QuotaExceededError` | no |
| 403 | `PermissionDeniedError` | no |
| 404 | `NotFoundError` | no |
| 429 | `RateLimitError` | yes, after `Retry-After` |
| 500, 502 | `ServerError` | yes, exponential backoff |
| 503 | `ServiceUnavailableError` | yes, after `Retry-After` |
| — | `APIConnectionError` (network, timeout) | yes, exponential backoff |

All of them derive from `ApiautoError`. Retries follow the
[API's error guide](https://apiauto.space/en/docs/errors/): `max_retries=2` by default, a wait of at most
60 seconds; `Client(max_retries=0)` turns them off. Other options: `Client(api_key=..., base_url=...,
timeout=30.0, http_client=httpx.Client(...))`.

### Photos

`car["photos"]` are signed links that work for about a day. Store the car's `id`, not the links, and
fetch a fresh record with `client.car(id)` when you need the photos again. Photo requests are free and
may redirect to the original host, so follow redirects when downloading them.

### Prices are decimal strings

Prices, dollar prices and percentages come as strings such as `"23900000.00"` so no precision is lost.
Convert them with `Decimal`:

```python
from decimal import Decimal

total = sum(Decimal(car["price_usd"]) for car in page["items"] if car["price_usd"])
```

## A record

A real Encar car from the [documentation](https://apiauto.space/en/docs/record/), shortened: two photo
links and a few `raw` fields.

```json
{
  "id": "encar:43020893",
  "market": "kr",
  "source": "encar",
  "source_id": "43020893",
  "title": "2020 Kia Mohave The Master 3.0 4WD 7-seater Masters",
  "brand": "Kia",
  "model": "Mohave",
  "generation": "Mohave The Master",
  "trim": "3.0 4WD 7-seater Masters",
  "year": 2020,
  "mileage_km": 93724,
  "fuel": "diesel",
  "transmission": null,
  "engine_cc": null,
  "body_type": null,
  "color": null,
  "vin": null,
  "price": {"amount": "23900000.00", "currency": "KRW"},
  "price_usd": "18033.96",
  "location": {"country": "KR", "region": "Gyeonggi", "city": null},
  "photos": [
    "https://api.apiauto.space/img/encar:43020893/1.jpg?exp=…&sig=…",
    "https://api.apiauto.space/img/encar:43020893/2.jpg?exp=…&sig=…"
  ],
  "photo_count": 4,
  "listing_url": "https://fem.encar.com/cars/detail/43020893",
  "is_active": true,
  "first_seen_at": "2026-10-26T04:37:32.553458Z",
  "last_seen_at": "2026-10-26T04:37:32.553458Z",
  "disappeared_at": null,
  "updated_at": "2026-10-26T04:37:32.553458Z",
  "source_mode": "replica",
  "raw": {"badge": "디젤 3.0 4WD 7인승", "form_year": "202004", "sell_type": "normal", "has_accident": false}
}
```

The fields each source adds are described on the [Encar API](https://apiauto.space/en/encar-api/),
[Che168 API](https://apiauto.space/en/che168-api/), [Copart API](https://apiauto.space/en/copart-api/) and
[IAAI API](https://apiauto.space/en/iaai-api/) pages.

## Methods

| Method | Endpoint | Returns | Quota |
| --- | --- | --- | --- |
| `cars(market, **filters)` | `GET /v1/cars` | `CarsPage`: `items`, `next_cursor`, `count` | per car |
| `iter_cars(market, *, max_items=None, **filters)` | `GET /v1/cars` | iterator of `Car` | per car |
| `car(car_id)` | `GET /v1/cars/{id}` | `Car` | 1 |
| `changes(market, since, *, type, min_pct, limit, cursor)` | `GET /v1/changes` | `ChangesPage` | per event |
| `iter_changes(market, since, *, type, min_pct, limit, max_items)` | `GET /v1/changes` | iterator of `Change` | per event |
| `brands(market)` | `GET /v1/references/brands` | list of `{name, count}` | free |
| `models(market, brand)` | `GET /v1/references/models` | list of `{name, count}` | free |
| `dictionaries()` | `GET /v1/references/dictionaries` | field → canonical value → synonyms | free |
| `markets()` | `GET /v1/references/markets` | list of `Market` | free |
| `usage()` | `GET /v1/usage` | `Usage` | free |
| `us_live(*, make, model, year_min, year_max, price_max, page)` | `GET /v1/us/live` | list of `Car` | own counter |

The API reference: [apiauto.space/en/docs](https://apiauto.space/en/docs/) and the
[OpenAPI schema](https://api.apiauto.space/openapi.json).

## Other languages

| Language | Package | Repository |
| --- | --- | --- |
| Python | `pip install apiauto-space` | [apiauto-space/apiauto-python](https://github.com/apiauto-space/apiauto-python) |
| JavaScript, TypeScript | `npm install apiauto` | [apiauto-space/apiauto-js](https://github.com/apiauto-space/apiauto-js) |
| curl, PHP and more | — | [apiauto-space/encar-api-examples](https://github.com/apiauto-space/encar-api-examples) |

## По-русски

`apiauto` — Python-клиент для API Encar, Che168, Copart и IAAI, без парсинга: объявления о подержанных
автомобилях из Южной Кореи, Китая и с аукционов США приходят в одном формате JSON через
[apiauto.space](https://apiauto.space/). Клиент умеет искать по марке, модели, году, цене и пробегу,
сам проходит по страницам курсором, повторяет запрос при 429 и 503 и работает в синхронном и асинхронном
коде. Бесплатный демо-ключ на сутки выдаёт Telegram-бот
[@apiautospace_bot](https://t.me/apiautospace_bot?start=demo); сохраните его в переменной `APIAUTO_KEY`
и держите на сервере, не в браузере. Документация на русском: [apiauto.space/docs](https://apiauto.space/docs/).

```bash
pip install apiauto-space
```

```python
import apiauto

client = apiauto.Client()  # ключ из APIAUTO_KEY
for car in client.cars("kr", brand="Kia", year_min=2021, limit=20)["items"]:
    print(car["title"], car["price"]["amount"], car["price"]["currency"])
```

## License

[MIT](https://github.com/apiauto-space/apiauto-python/blob/main/LICENSE) © 2026 apiauto.space

## Disclaimer

This is an unofficial client of the apiauto.space API. It is not affiliated with, endorsed by or
sponsored by Encar, Che168, Autohome, Copart or IAAI; their names are used only to describe where the
listings come from, and all trademarks belong to their owners. Use of the data is subject to the
[apiauto.space terms](https://apiauto.space/en/offer/).
