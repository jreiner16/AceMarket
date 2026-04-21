"""Persistent storage via PostgreSQL (Supabase)."""
import json
import logging
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: Optional[ThreadedConnectionPool] = None
_pool_lock = Lock()


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(1, 10, DATABASE_URL)
    return _pool


def _conn():
    return _get_pool().getconn()


def _put(conn):
    _get_pool().putconn(conn)


def init_db():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    user_id TEXT PRIMARY KEY,
                    settings_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    user_id TEXT PRIMARY KEY,
                    cash DOUBLE PRECISION NOT NULL DEFAULT 0,
                    positions_json TEXT NOT NULL DEFAULT '[]',
                    trade_log_json TEXT NOT NULL DEFAULT '[]',
                    equity_curve_json TEXT NOT NULL DEFAULT '[]',
                    realized_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS strategies_user_id_idx ON strategies (user_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    symbols_json TEXT NOT NULL DEFAULT '[]',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    results_json TEXT NOT NULL DEFAULT '[]',
                    portfolio_json TEXT NOT NULL DEFAULT '{}',
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS runs_user_id_idx ON runs (user_id)
            """)
        conn.commit()
        logger.info("Database tables ready")
    finally:
        _put(conn)


def close_conn():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


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
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT settings_json FROM settings WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
        if row:
            stored = json.loads(row[0])
            data = {**DEFAULT_SETTINGS, **stored}
            if "watchlist" not in data or not isinstance(data.get("watchlist"), list):
                data["watchlist"] = DEFAULT_WATCHLIST.copy()
            return data
        out = DEFAULT_SETTINGS.copy()
        out["watchlist"] = DEFAULT_WATCHLIST.copy()
        return out
    finally:
        _put(conn)


def save_settings(user_id: str, settings: dict):
    merged = {**DEFAULT_SETTINGS, **settings}
    if "watchlist" not in merged or not isinstance(merged.get("watchlist"), list):
        merged["watchlist"] = DEFAULT_WATCHLIST.copy()
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO settings (user_id, settings_json)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET settings_json = EXCLUDED.settings_json
            """, (user_id, json.dumps(merged)))
        conn.commit()
    finally:
        _put(conn)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

def get_portfolio_state(user_id: str) -> Optional[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cash, positions_json, trade_log_json, equity_curve_json, realized_json "
                "FROM portfolios WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "cash": float(row[0]),
            "positions": json.loads(row[1] or "[]"),
            "trade_log": json.loads(row[2] or "[]"),
            "equity_curve": json.loads(row[3] or "[]"),
            "realized": json.loads(row[4] or "{}"),
        }
    finally:
        _put(conn)


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
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO portfolios (user_id, cash, positions_json, trade_log_json, equity_curve_json, realized_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    cash = EXCLUDED.cash,
                    positions_json = EXCLUDED.positions_json,
                    trade_log_json = EXCLUDED.trade_log_json,
                    equity_curve_json = EXCLUDED.equity_curve_json,
                    realized_json = EXCLUDED.realized_json
            """, (
                user_id,
                float(cash),
                json.dumps(positions_data),
                json.dumps(trade_log or []),
                json.dumps(equity_curve or []),
                json.dumps(realized_serializable),
            ))
        conn.commit()
    finally:
        _put(conn)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def get_strategies(user_id: str) -> list[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, code, created_at FROM strategies WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cur.fetchall()
        return [{"id": r[0], "name": r[1], "code": r[2], "created_at": r[3]} for r in rows]
    finally:
        _put(conn)


def create_strategy(user_id: str, name: str, code: str) -> dict:
    sid = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO strategies (id, user_id, name, code, created_at) VALUES (%s, %s, %s, %s, %s)",
                (sid, user_id, name, code, created_at)
            )
        conn.commit()
    finally:
        _put(conn)
    return {"id": sid, "name": name, "code": code}


def get_strategy(user_id: str, strategy_id: str) -> Optional[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, code FROM strategies WHERE id = %s AND user_id = %s",
                (strategy_id, user_id)
            )
            row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "code": row[2]}
    finally:
        _put(conn)


def update_strategy(user_id: str, strategy_id: str, name: Optional[str], code: Optional[str]) -> Optional[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            if name is not None and code is not None:
                cur.execute(
                    "UPDATE strategies SET name = %s, code = %s WHERE id = %s AND user_id = %s RETURNING id, name, code",
                    (name, code, strategy_id, user_id)
                )
            elif name is not None:
                cur.execute(
                    "UPDATE strategies SET name = %s WHERE id = %s AND user_id = %s RETURNING id, name, code",
                    (name, strategy_id, user_id)
                )
            elif code is not None:
                cur.execute(
                    "UPDATE strategies SET code = %s WHERE id = %s AND user_id = %s RETURNING id, name, code",
                    (code, strategy_id, user_id)
                )
            else:
                cur.execute(
                    "SELECT id, name, code FROM strategies WHERE id = %s AND user_id = %s",
                    (strategy_id, user_id)
                )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "code": row[2]}
    finally:
        _put(conn)


def delete_strategy(user_id: str, strategy_id: str) -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM strategies WHERE id = %s AND user_id = %s",
                (strategy_id, user_id)
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        _put(conn)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def save_run(user_id: str, run_data: dict) -> str:
    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO runs (id, user_id, strategy_id, strategy_name, symbols_json,
                    start_date, end_date, results_json, portfolio_json, metrics_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                run_id,
                user_id,
                str(run_data["strategy_id"]),
                run_data["strategy"],
                json.dumps(run_data.get("symbols", [])),
                run_data["start_date"],
                run_data["end_date"],
                json.dumps(run_data.get("results", [])),
                json.dumps(run_data.get("portfolio", {})),
                json.dumps(run_data.get("metrics", {})),
                created_at,
            ))
        conn.commit()
    finally:
        _put(conn)
    return run_id


def get_runs(user_id: str, limit: int = 25) -> list[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, strategy_id, strategy_name, symbols_json,
                    start_date, end_date, metrics_json, portfolio_json
                FROM runs WHERE user_id = %s
                ORDER BY created_at DESC LIMIT %s
            """, (user_id, limit))
            rows = cur.fetchall()
    finally:
        _put(conn)

    out = []
    for r in rows:
        try:
            metrics = json.loads(r[7] or "{}")
            portfolio = json.loads(r[8] or "{}")
        except (json.JSONDecodeError, TypeError):
            metrics, portfolio = {}, {}
        equity = metrics.get("equity", {})
        trades = metrics.get("trades", {})
        run_type = portfolio.get("run_type", "backtest")
        out.append({
            "id": r[0],
            "created_at": r[1],
            "strategy": r[3],
            "strategy_id": r[2],
            "symbols": json.loads(r[4] or "[]"),
            "start_date": r[5],
            "end_date": r[6],
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
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, strategy_id, strategy_name, symbols_json,
                    start_date, end_date, results_json, portfolio_json, metrics_json
                FROM runs WHERE id = %s AND user_id = %s
            """, (run_id, user_id))
            row = cur.fetchone()
    finally:
        _put(conn)

    if not row:
        return None
    return {
        "id": row[0],
        "created_at": row[1],
        "started_at": row[1],
        "ended_at": row[1],
        "strategy_id": row[2],
        "strategy": row[3],
        "symbols": json.loads(row[4] or "[]"),
        "start_date": row[5],
        "end_date": row[6],
        "results": json.loads(row[7] or "[]"),
        "portfolio": json.loads(row[8] or "{}"),
        "metrics": json.loads(row[9] or "{}"),
    }


def clear_runs(user_id: str):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM runs WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        _put(conn)
