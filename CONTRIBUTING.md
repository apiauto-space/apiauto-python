# Contributing

Bug reports and pull requests are welcome at
[github.com/apiauto-space/apiauto-python](https://github.com/apiauto-space/apiauto-python/issues).
For questions about the API itself, data or plans, write to
[@apiautospace_bot](https://t.me/apiautospace_bot).

## Development

```bash
git clone https://github.com/apiauto-space/apiauto-python
cd apiauto-python
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e . --group dev
```

Before sending a pull request, run the same checks as CI:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Unit tests use `httpx.MockTransport` and never touch the network. `tests/test_live.py` runs
against the real API only when `APIAUTO_KEY` is set and spends at most 10 records.

Keep the client thin: it mirrors the API and adds no logic of its own beyond pagination,
retries and error mapping. Add a test for every change and a line to `CHANGELOG.md`.
