"""Basic API smoke tests."""
import os
from unittest.mock import patch

os.environ["DISABLE_AUTH"] = "1"
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import pytest
from fastapi.testclient import TestClient
from api import app


@pytest.fixture(scope="module")
def client():
    with patch("db.init_db"), patch("db.close_conn"):
        with TestClient(app) as c:
            yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_returns_data(client):
    r = client.get("/api/v1/search?q=AAPL")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_stock_data(client):
    r = client.get("/api/v1/stock/AAPL?limit=10")
    if r.status_code == 404:
        pytest.skip("yfinance may be rate-limited or unavailable")
    assert r.status_code == 200
    data = r.json()
    assert "candles" in data
    assert "symbol" in data
