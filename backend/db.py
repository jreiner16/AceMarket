"""Persistent storage via Convex (https://convex.dev).
All CRUD is delegated to Convex mutations/queries over HTTP.
"""
import json
import logging
from typing import Optional

import httpx

from config import CONVEX_URL, CONVEX_DEPLOY_KEY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Convex HTTP API helpers
# ---------------------------------------------------------------------------

def _call(kind: str, path: str, args: dict):
    """Call a Convex query or mutation via the HTTP API."""
    resp = httpx.post(
        f"{CONVEX_URL}/api/{kind}",
        headers={"Authorization": f"Convex {CONVEX_DEPLOY_KEY}"},
        json={"path": path, "args": args, "format": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Convex {kind} '{path}' failed: {data.get('errorMessage', data)}")
    return data["value"]


def _query(path: str, args: dict):
    return _call("query", path, args)


def _mutation(path: str, args: dict):
    return _call("mutation", path, args)


# ---------------------------------------------------------------------------
# Lifecycle (no-ops — Convex needs no local init or connection teardown)
# ---------------------------------------------------------------------------

def init_db():
    logger.info("Using Convex backend — no local DB init required")


def close_conn():
    pass


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "TSLA"]
DEFAULT_SETTINGS = {
    "initial_cash": 100000,
    "slippage": 0.0,
    "commission": 0.0,
    "share_min_pct": 10,
    "allow_short": True,
    "max_positions": 0,
    "max_position_pct": 0.0,
    "min_cash_reserve_pct": 0.0,
    "min_trade_value": 0.0,
    "max_trade_value": 0.0,
    "max_order_qty": 0,
    "short_margin_requirement": 1.5,
    "auto_liquidate_end": True,
    "block_lookahead": True,
}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_settings(user_id: str) -> dict:
    raw = _query("settings:getSettings", {"userId": user_id})
    if raw:
        stored = json.loads(raw)
        data = {**DEFAULT_SETTINGS, **stored}
        if "watchlist" not in data or not isinstance(data.get("watchlist"), list):
            data["watchlist"] = DEFAULT_WATCHLIST.copy()
        if "share_min_pct" not in stored and "share_precision" in stored:
            data["share_min_pct"] = [100, 10, 1][min(int(stored["share_precision"]), 2)]
        return data
    out = DEFAULT_SETTINGS.copy()
    out["watchlist"] = DEFAULT_WATCHLIST.copy()
    return out


def save_settings(user_id: str, settings: dict):
    merged = {**DEFAULT_SETTINGS, **settings}
    if "watchlist" not in merged or not isinstance(merged.get("watchlist"), list):
        merged["watchlist"] = DEFAULT_WATCHLIST.copy()
    _mutation("settings:saveSettings", {"userId": user_id, "settingsJson": json.dumps(merged)})


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

def get_portfolio_state(user_id: str) -> Optional[dict]:
    row = _query("portfolios:getPortfolio", {"userId": user_id})
    if not row:
        return None
    return {
        "cash": float(row["cash"]),
        "positions": json.loads(row["positionsJson"] or "[]"),
        "trade_log": json.loads(row["tradeLogJson"] or "[]"),
        "equity_curve": json.loads(row["equityCurveJson"] or "[]"),
        "realized": json.loads(row["realizedJson"] or "{}"),
    }


def save_portfolio_state(
    user_id: str,
    cash: float,
    positions: list,
    trade_log: list,
    equity_curve: list,
    realized: dict,
):
    positions_data = []
    for p in positions or []:
        if not isinstance(p, dict):
            continue
        stock = p.get("stock")
        symbol = getattr(stock, "symbol", None) if stock else p.get("symbol")
        if not symbol:
            continue
        symbol = str(symbol).upper()
        qty = float(p.get("quantity", 0))
        if qty == 0:
            continue
        positions_data.append({
            "symbol": symbol,
            "quantity": qty,
            "avg_price": float(p.get("avg_price", 0)),
            "realized_pnl": float(p.get("realized_pnl", 0)),
        })

    realized_serializable = {k: float(v) for k, v in (realized or {}).items()}
    _mutation("portfolios:savePortfolio", {
        "userId": user_id,
        "cash": float(cash),
        "positionsJson": json.dumps(positions_data),
        "tradeLogJson": json.dumps(trade_log or []),
        "equityCurveJson": json.dumps(equity_curve or []),
        "realizedJson": json.dumps(realized_serializable),
    })


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def get_strategies(user_id: str) -> list[dict]:
    rows = _query("strategies:getStrategies", {"userId": user_id})
    return [
        {"id": r["id"], "name": r["name"], "code": r["code"], "created_at": r["createdAt"]}
        for r in (rows or [])
    ]


def create_strategy(user_id: str, name: str, code: str) -> dict:
    result = _mutation("strategies:createStrategy", {"userId": user_id, "name": name, "code": code})
    return {"id": result["id"], "name": result["name"], "code": result["code"]}


def get_strategy(user_id: str, strategy_id: str) -> Optional[dict]:
    result = _query("strategies:getStrategy", {"userId": user_id, "strategyId": strategy_id})
    if not result:
        return None
    return {"id": result["id"], "name": result["name"], "code": result["code"]}


def update_strategy(user_id: str, strategy_id: str, name: Optional[str], code: Optional[str]) -> Optional[dict]:
    result = _mutation("strategies:updateStrategy", {
        "userId": user_id,
        "strategyId": strategy_id,
        "name": name,
        "code": code,
    })
    if not result:
        return None
    return {"id": result["id"], "name": result["name"], "code": result["code"]}


def delete_strategy(user_id: str, strategy_id: str) -> bool:
    return bool(_mutation("strategies:deleteStrategy", {"userId": user_id, "strategyId": strategy_id}))


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def save_run(user_id: str, run_data: dict) -> str:
    run_id = _mutation("runs:saveRun", {
        "userId": user_id,
        "strategyId": str(run_data["strategy_id"]),
        "strategyName": run_data["strategy"],
        "symbolsJson": json.dumps(run_data.get("symbols", [])),
        "startDate": run_data["start_date"],
        "endDate": run_data["end_date"],
        "resultsJson": json.dumps(run_data.get("results", [])),
        "portfolioJson": json.dumps(run_data.get("portfolio", {})),
        "metricsJson": json.dumps(run_data.get("metrics", {})),
    })
    return run_id


def get_runs(user_id: str, limit: int = 25) -> list[dict]:
    rows = _query("runs:getRuns", {"userId": user_id, "limit": limit})
    out = []
    for r in (rows or []):
        try:
            metrics = json.loads(r["metricsJson"] or "{}")
            portfolio = json.loads(r["portfolioJson"] or "{}")
        except (json.JSONDecodeError, TypeError):
            metrics, portfolio = {}, {}
        equity = metrics.get("equity", {})
        trades = metrics.get("trades", {})
        run_type = portfolio.get("run_type", "backtest")
        out.append({
            "id": r["id"],
            "created_at": r["createdAt"],
            "strategy": r["strategyName"],
            "strategy_id": r["strategyId"],
            "symbols": json.loads(r["symbolsJson"] or "[]"),
            "start_date": r["startDate"],
            "end_date": r["endDate"],
            "run_type": run_type,
            "start_value": equity.get("start_value"),
            "end_value": equity.get("end_value"),
            "pnl": equity.get("pnl"),
            "total_return_pct": equity.get("total_return_pct"),
            "max_drawdown_pct": equity.get("max_drawdown_pct"),
            "trades": trades.get("trades"),
            "exits": trades.get("exits"),
            "win_rate_pct": trades.get("win_rate_pct"),
            "prob_profit_pct": portfolio.get("prob_profit_pct"),
        })
    return out


def get_run(user_id: str, run_id: str) -> Optional[dict]:
    row = _query("runs:getRun", {"userId": user_id, "runId": run_id})
    if not row:
        return None
    created = row["createdAt"]
    return {
        "id": row["id"],
        "created_at": created,
        "started_at": created,
        "ended_at": created,
        "strategy_id": row["strategyId"],
        "strategy": row["strategyName"],
        "symbols": json.loads(row["symbolsJson"] or "[]"),
        "start_date": row["startDate"],
        "end_date": row["endDate"],
        "results": json.loads(row["resultsJson"] or "[]"),
        "portfolio": json.loads(row["portfolioJson"] or "{}"),
        "metrics": json.loads(row["metricsJson"] or "{}"),
    }


def clear_runs(user_id: str):
    _mutation("runs:clearRuns", {"userId": user_id})
