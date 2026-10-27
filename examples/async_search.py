"""Query the three markets concurrently with AsyncClient.

    pip install apiauto
    export APIAUTO_KEY=...
    python async_search.py

Costs 3 data requests on a demo key (up to 9 records on a paid plan). The demo
allows 1 request per second: the client waits and retries on 429 by itself.
"""

import asyncio

import apiauto


async def newest(client: apiauto.AsyncClient, market: apiauto.MarketCode) -> list[apiauto.Car]:
    page = await client.cars(market, brand="Toyota", has_photos=True, limit=3)
    return page["items"]


async def main() -> None:
    async with apiauto.AsyncClient() as client:
        markets = await client.markets()  # free: freshness of every market
        for m in markets:
            print(f"{m['market']}: {m['active_cars']} active cars, data age {m['data_age_seconds']} s")

        results = await asyncio.gather(*(newest(client, m) for m in ("kr", "cn", "us")))
        for cars in results:
            for car in cars:
                print(car["id"], car["title"], car["price"]["amount"], car["price"]["currency"])


if __name__ == "__main__":
    asyncio.run(main())
