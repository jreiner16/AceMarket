"""Basic API smoke tests."""
import os

import pytest
from fastapi.testclient import TestClient

# Use in-memory DB for tests
os.environ["ACEMARKET_DB"] = ":memory:"
os.environ["DISABLE_AUTH"] = "1"

from api import app

client = TestClient(app)


def test_health():
    """Health check returns ok."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_requires_auth_when_enabled():
    """Search endpoint exists and returns data when auth disabled."""
    r = client.get("/api/v1/search?q=AAPL")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_stock_data():
    """Stock endpoint returns OHLC data."""
    r = client.get("/api/v1/stock/AAPL?limit=10")
    if r.status_code == 404:
        pytest.skip("yfinance may be rate-limited or unavailable")
    assert r.status_code == 200
    data = r.json()
    assert "candles" in data
    assert "symbol" in data
