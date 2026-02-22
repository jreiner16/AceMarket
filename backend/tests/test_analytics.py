"""Unit tests for analytics module."""
import pytest
from analytics import (
    compute_equity_metrics,
    compute_trade_metrics,
    compute_report,
    compute_symbol_breakdown,
)


def test_compute_equity_metrics_empty():
    m = compute_equity_metrics([], 1000)
    assert m["start_value"] == 1000
    assert m["end_value"] == 1000
    assert m["pnl"] == 0
    assert m["total_return_pct"] == 0


def test_compute_equity_metrics_simple():
    curve = [
        {"i": 0, "v": 1000, "time": "2023-01-01"},
        {"i": 1, "v": 1100, "time": "2023-06-01"},
        {"i": 2, "v": 1050, "time": "2023-12-01"},
    ]
    m = compute_equity_metrics(curve, 1000)
    assert m["start_value"] == 1000
    assert m["end_value"] == 1050
    assert m["pnl"] == 50
    assert m["total_return_pct"] == 5.0
    assert m["max_drawdown_pct"] < 0
    assert "sharpe_annual" in m
    assert "sortino_annual" in m
    assert "calmar_annual" in m


def test_compute_trade_metrics_empty():
    m = compute_trade_metrics([])
    assert m["trades"] == 0
    assert m["exits"] == 0
    assert m["win_rate_pct"] == 0


def test_compute_trade_metrics():
    trades = [
        {"type": "long", "stock": "AAPL", "realized_pnl": 0, "cost": 1000},
        {"type": "exit", "stock": "AAPL", "realized_pnl": 50, "amount": 1050},
        {"type": "exit", "stock": "AAPL", "realized_pnl": -20, "amount": 980},
    ]
    m = compute_trade_metrics(trades)
    assert m["trades"] == 3
    assert m["exits"] == 2
    assert m["wins"] == 1
    assert m["losses"] == 1
    assert m["win_rate_pct"] == 50.0
    assert "turnover" in m


def test_compute_symbol_breakdown():
    trades = [
        {"type": "long", "stock": "AAPL", "realized_pnl": 0},
        {"type": "exit", "stock": "AAPL", "realized_pnl": 100},
        {"type": "exit", "stock": "MSFT", "realized_pnl": -30},
    ]
    by = compute_symbol_breakdown(trades)
    assert len(by) == 2
    aapl = next(b for b in by if b["symbol"] == "AAPL")
    assert aapl["trades"] == 2
    assert aapl["exits"] == 1
    assert aapl["net_realized"] == 100


def test_compute_report():
    curve = [{"i": 0, "v": 1000}, {"i": 1, "v": 1100}]
    trades = [{"type": "exit", "stock": "AAPL", "realized_pnl": 100}]
    r = compute_report(trades, curve, 1000)
    assert "equity" in r
    assert "trades" in r
    assert "symbols" in r
    assert r["equity"]["end_value"] == 1100
    assert r["trades"]["exits"] == 1
