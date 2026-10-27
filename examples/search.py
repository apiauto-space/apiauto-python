"""Search Encar, Che168 and US auction lots with one client.

    pip install apiauto
    export APIAUTO_KEY=...   # free demo key: https://t.me/apiautospace_bot?start=demo
    python search.py

Costs 3 data requests on a demo key (up to 15 records on a paid plan).
"""

from decimal import Decimal

import apiauto


def show(car: apiauto.Car) -> None:
    usd = f"${Decimal(car['price_usd']):,.0f}" if car["price_usd"] else "no price"
    print(f"  {car['id']:<20} {car['title'][:50]:<50} {usd}")


def main() -> None:
    with apiauto.Client() as client:
        # Korea, Encar: Kia Sorento from 2021 between 10 and 30 million KRW, newest first.
        # The lower bound skips leases that Encar lists with a monthly payment as the price.
        page = client.cars(
            "kr",
            brand="Kia",
            model="Sorento",
            year_min=2021,
            price_min=10_000_000,
            price_max=30_000_000,
            limit=5,
        )
        print(f"Encar: {page['count']} matching cars")
        for car in page["items"]:
            show(car)

        # China, Che168: BYD with photos, newest in the catalog first.
        print("Che168:")
        for car in client.cars("cn", brand="BYD", has_photos=True, limit=5)["items"]:
            show(car)

        # USA, Copart and IAAI: upcoming lots; damage and sale date are in raw.
        print("Copart and IAAI:")
        for car in client.cars("us", brand="Toyota", model="Camry", year_min=2020, limit=5)["items"]:
            show(car)
            print(f"  {'':<20} damage: {car['raw'].get('damage_main')}, sale: {car['raw'].get('sale_date')}")

        info = client.last_response
        if info is not None:
            print(f"Quota left: {info.quota_remaining} of {info.quota_limit}, renews {info.quota_reset}")


if __name__ == "__main__":
    main()
