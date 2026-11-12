"""Market-data providers.

Two sources, one interface:

* ``FixtureProvider`` -- a bundled snapshot in the exact shape of Base's
  public Tokenized Stocks API. Used for the deterministic demo and tests.
  Prices in the fixture are *scenario* values for simulation, clearly
  labelled as such; they are not live quotes.
* ``BaseTokenizedStocksProvider`` -- reads the real, read-only, key-less
  Tokenized Stocks API documented at docs.base.org/sdks/tokenized-stocks.
  The base URL is taken from ``--api-url`` / ``BASE_TOKENIZED_STOCKS_API_URL``
  (copy it from the official API reference) -- StockPilot never guesses
  endpoints and never requires an API key.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from .models import StockQuote, parse_ts

Fetcher = Callable[[str], dict[str, Any]]


def http_get_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class FixtureProvider:
    name = "fixture"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.as_of = parse_ts(payload.get("as_of"))
        self.records = payload.get("tokens") or []

    def load(self) -> tuple[dict[str, StockQuote], Optional[datetime], str]:
        quotes: dict[str, StockQuote] = {}
        for record in self.records:
            quote = StockQuote.from_api_record(record, source=self.name)
            if quote.symbol:
                quotes[quote.symbol] = quote
        return quotes, self.as_of, f"fixture:{self.path.name}"


class BaseTokenizedStocksProvider:
    """Read-only client for the official Tokenized Stocks API.

    Follows the documented contract: GET / returns ``tokens`` plus an
    optional ``next_page_token``; pass it back as ``page_token`` until it
    is omitted. Missing fields are normal (the API omits defaults), and a
    missing ``nav_price`` means the record is unusable -- never invented.
    """

    name = "base-tokenized-stocks-api"

    def __init__(self, base_url: str, fetcher: Fetcher = http_get_json, page_size: int = 100):
        self.base_url = base_url.rstrip("/")
        self.fetcher = fetcher
        self.page_size = page_size

    def _page_url(self, page_token: Optional[str]) -> str:
        params = {"page_size": str(self.page_size)}
        if page_token:
            params["page_token"] = page_token
        return f"{self.base_url}/?{urllib.parse.urlencode(params)}"

    def load(self) -> tuple[dict[str, StockQuote], Optional[datetime], str]:
        quotes: dict[str, StockQuote] = {}
        page_token: Optional[str] = None
        pages = 0
        while True:
            payload = self.fetcher(self._page_url(page_token))
            pages += 1
            for record in payload.get("tokens") or []:
                if record.get("nav_price") is None:
                    continue  # no reference value -> not tradeable data; skip, never fabricate
                quote = StockQuote.from_api_record(record, source=self.name)
                if quote.symbol:
                    quotes[quote.symbol] = quote
            page_token = payload.get("next_page_token")
            if not page_token or pages > 50:
                break
        return quotes, None, f"{self.name} ({pages} page(s), {len(quotes)} usable records)"


def provider_from_args(api_url: Optional[str], fixture_path: str | Path):
    url = api_url or os.environ.get("BASE_TOKENIZED_STOCKS_API_URL")
    if url:
        return BaseTokenizedStocksProvider(url)
    return FixtureProvider(fixture_path)
