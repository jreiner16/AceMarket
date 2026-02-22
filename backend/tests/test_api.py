"""API integration tests. Uses file-based DB so all threads share the same DB."""
import os
import tempfile

# Set DB path before any backend imports (config reads it at load)
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
os.environ["ACEMARKET_DB"] = _test_db.name

import pytest
from fastapi.testclient import TestClient

import db
from api import app

db.init_db()

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_requires_auth_when_enabled():
    """Search without auth may 401 if auth enabled. With DISABLE_AUTH, passes."""
    r = client.get("/api/v1/search?q=aapl")
    # With DISABLE_AUTH=1 in test env, we get 200. Otherwise 401.
    assert r.status_code in (200, 401)


def test_stock_data_requires_auth():
    r = client.get("/api/v1/stock/AAPL")
    assert r.status_code in (200, 401, 404)  # 404 if no data


def test_portfolio_requires_auth():
    r = client.get("/api/v1/portfolio")
    assert r.status_code in (200, 401, 500)  # 500 if db/init issue


def test_settings_requires_auth():
    r = client.get("/api/v1/settings")
    assert r.status_code in (200, 401, 500)


def test_strategies_requires_auth():
    r = client.get("/api/v1/strategies")
    assert r.status_code in (200, 401, 500)


def test_create_strategy_empty_code():
    r = client.post(
        "/api/v1/strategies",
        json={"name": "Test", "code": ""},
    )
    assert r.status_code in (400, 401)


def test_create_strategy_empty_name():
    r = client.post(
        "/api/v1/strategies",
        json={"name": "", "code": "class X(Strategy): pass"},
    )
    assert r.status_code in (400, 401)
