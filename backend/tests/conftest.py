"""Pytest fixtures and mocks. Mocks data provider to avoid network calls in tests."""
import pytest
import pandas as pd
import numpy as np


def _make_fake_df():
    """Create fake OHLC DataFrame for testing."""
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    n = len(dates)
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    open_ = np.roll(close, 1)
    open_[0] = 100
    high = np.maximum(open_, close) + np.abs(np.random.randn(n))
    low = np.minimum(open_, close) - np.abs(np.random.randn(n))
    volume = np.random.randint(1e6, 1e7, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=pd.to_datetime(dates),
    )


@pytest.fixture(autouse=True)
def mock_data_provider(monkeypatch):
    """Mock get_ohlc at point of use (stock module) to avoid network calls."""
    fake_df = _make_fake_df()

    def mock_get_ohlc(symbol, from_date=None, to_date=None):
        return fake_df.copy()

    monkeypatch.setattr("stock.get_ohlc", mock_get_ohlc)
