"""Python client for the apiauto.space used-car API.

Encar (South Korea), Che168 (China), Copart and IAAI (USA) listings in one
JSON record format::

    import apiauto

    with apiauto.Client() as client:  # the key comes from APIAUTO_KEY
        for car in client.cars("kr", brand="Kia", year_min=2020, limit=20)["items"]:
            print(car["id"], car["title"], car["price"])

Unofficial: not affiliated with Encar, Che168/Autohome, Copart or IAAI.
"""

from ._async_client import AsyncClient
from ._base import ResponseInfo
from ._client import Client
from ._version import __version__
from .errors import (
    ApiautoError,
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
)
from .types import (
    Car,
    CarFilters,
    CarsPage,
    Change,
    ChangesPage,
    ChangeType,
    Dictionaries,
    Location,
    Market,
    MarketCode,
    Price,
    ReferenceItem,
    Sort,
    Usage,
    UsageMarket,
)

__all__ = [
    "APIConnectionError",
    "ApiautoError",
    "AsyncClient",
    "AuthenticationError",
    "BadRequestError",
    "Car",
    "CarFilters",
    "CarsPage",
    "Change",
    "ChangeType",
    "ChangesPage",
    "Client",
    "Dictionaries",
    "Location",
    "Market",
    "MarketCode",
    "NotFoundError",
    "PermissionDeniedError",
    "Price",
    "QuotaExceededError",
    "RateLimitError",
    "ReferenceItem",
    "ResponseInfo",
    "ServerError",
    "ServiceUnavailableError",
    "Sort",
    "Usage",
    "UsageMarket",
    "__version__",
]
