# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-27

First release.

### Added

- `Client` and `AsyncClient` for the apiauto.space API: Encar (Korea), Che168 (China),
  Copart and IAAI (USA).
- Catalog search with typed filters: `cars()`, `iter_cars()` with `max_items`, `car()`.
- Change feed: `changes()` and `iter_changes()`; `since` takes a `datetime` or an ISO 8601 string.
- References and usage: `brands()`, `models()`, `dictionaries()`, `markets()`, `usage()`.
- Live US search: `us_live()`.
- Exceptions per API error (`BadRequestError`, `AuthenticationError`, `QuotaExceededError`,
  `PermissionDeniedError`, `NotFoundError`, `RateLimitError`, `ServerError`,
  `ServiceUnavailableError`, `APIConnectionError`).
- Retries on 429 and 503 after `Retry-After`, and on 5xx and network errors with backoff.
- Quota and rate-limit headers in `client.last_response`.
- `TypedDict` types for every response and `py.typed`.

[0.1.0]: https://github.com/apiauto-space/apiauto-python/releases/tag/v0.1.0
