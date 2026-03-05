"""Test that backtest/Monte Carlo results serialize to JSON (no int64/float64). Run in ~2 sec."""
import json
import numpy as np
import pytest


def _json_default(o):
    if hasattr(o, "item") and callable(getattr(o, "item")):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _to_native(obj):
    return json.loads(json.dumps(obj, default=_json_default))


def test_to_native_handles_numpy():
    """Must convert numpy types to native Python."""
    result = {
        "ok": True,
        "run_id": np.int64(42),
        "results": [
            {"symbol": "AAPL", "pnl": np.float64(123.45), "start_value": 100000, "end_value": np.float64(100123.45)},
            {"symbol": "MSFT", "pnl": np.float64(-50.0), "start_value": 100000, "end_value": np.float64(99950.0)},
        ],
    }
    out = _to_native(result)
    assert out["run_id"] == 42
    assert isinstance(out["run_id"], int)
    assert isinstance(out["results"][0]["pnl"], float)
    assert out["results"][0]["pnl"] == 123.45
    json.dumps(out)


def test_to_native_handles_nested():
    """Nested dicts and lists with numpy."""
    data = {"metrics": {"equity": {"pnl": np.float64(1.5), "trades": np.int64(10)}}}
    out = _to_native(data)
    json.dumps(out)
    assert isinstance(out["metrics"]["equity"]["pnl"], float)
    assert isinstance(out["metrics"]["equity"]["trades"], int)


def test_matches_api_implementation():
    """Verify our test logic matches api._to_native."""
    from api import _to_native
    result = {"run_id": np.int64(99), "pnl": np.float64(1.5)}
    out = _to_native(result)
    assert out["run_id"] == 99 and isinstance(out["run_id"], int)
    assert out["pnl"] == 1.5 and isinstance(out["pnl"], float)
    json.dumps(out)
