"""Keep a local copy of a market fresh with the change feed.

    pip install apiauto
    export APIAUTO_KEY=...
    python sync_changes.py kr

The first run imports the catalog, then the script polls GET /changes once an
hour (the market copy is refreshed hourly, so polling more often makes no sense).
Here the "database" is a dict and the import stops at 100 cars: on a paid plan
drop max_items and pass limit=100 to copy a whole market.
"""

import sys
import time
from datetime import datetime, timezone
from typing import cast

import apiauto

catalog: dict[str, apiauto.Car] = {}


def import_market(client: apiauto.Client, market: apiauto.MarketCode) -> None:
    for car in client.iter_cars(market, max_items=100, limit=20):
        catalog[car["id"]] = car
    print(f"imported {len(catalog)} cars")


def apply_changes(client: apiauto.Client, market: apiauto.MarketCode, since: datetime) -> None:
    for event in client.iter_changes(market, since, limit=20):
        car_id = event["car_id"]
        if event["type"] == "added":
            catalog[car_id] = client.car(car_id)
        elif event["type"] == "disappeared":
            if car_id in catalog:
                catalog[car_id]["is_active"] = False  # sold or removed; kept by the API for 14 days
        elif car_id in catalog:  # price_drop or price_up
            catalog[car_id]["price"]["amount"] = event["new_price"]
        print(f"{event['at']} {event['type']:<12} {car_id} {event['pct'] or ''}")


def main() -> None:
    market = cast(apiauto.MarketCode, sys.argv[1] if len(sys.argv) > 1 else "kr")  # the client checks it

    with apiauto.Client() as client:
        since = datetime.now(timezone.utc)
        import_market(client, market)
        while True:
            time.sleep(3600)
            polled_at = datetime.now(timezone.utc)
            try:
                apply_changes(client, market, since)
            except apiauto.QuotaExceededError as error:
                sys.exit(f"Quota is spent until {error.reset_at}")
            except apiauto.ApiautoError as error:
                print(f"poll failed, will retry in an hour: {error}")
                continue
            since = polled_at


if __name__ == "__main__":
    main()
