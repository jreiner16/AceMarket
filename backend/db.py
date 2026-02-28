"""SQLite storage so portfolios, strategies, runs, and settings persiste across sessions"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH

_local = threading.local()


def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        # check_same_thread=True (default): each thread gets its own connection via thread-local.
        # Use --workers 1 with uvicorn when using SQLite (no multi-process support).
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=True)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


@contextmanager
def get_cursor():
    conn = _get_conn()
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db():
    """Create tables if they don't exist."""
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id TEXT PRIMARY KEY,
                settings_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                user_id TEXT PRIMARY KEY,
                cash REAL NOT NULL,
                positions_json TEXT NOT NULL,
                trade_log_json TEXT NOT NULL,
                equity_curve_json TEXT NOT NULL,
                realized_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                strategy_name TEXT NOT NULL,
                symbols_json TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                results_json TEXT NOT NULL,
                portfolio_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id)")


# --- Default settings ---
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


def get_settings(user_id: str) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT settings_json FROM settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
    if row:
        stored = json.loads(row["settings_json"])
        data = {**DEFAULT_SETTINGS, **stored}
        if "watchlist" not in data or not isinstance(data.get("watchlist"), list):
            data["watchlist"] = DEFAULT_WATCHLIST.copy()
        # Migrate share_precision -> share_min_pct only if user never set share_min_pct
        if "share_min_pct" not in stored and "share_precision" in stored:
            data["share_min_pct"] = [100, 10, 1][min(int(stored["share_precision"]), 2)]
        return data
    out = DEFAULT_SETTINGS.copy()
    out["watchlist"] = DEFAULT_WATCHLIST.copy()
    return out


def save_settings(user_id: str, settings: dict):
    """Save settings. Merge with defaults so we never drop keys (e.g. share_min_pct)."""
    merged = {**DEFAULT_SETTINGS, **settings}
    if "watchlist" not in merged or not isinstance(merged.get("watchlist"), list):
        merged["watchlist"] = DEFAULT_WATCHLIST.copy()
    with get_cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO settings (user_id, settings_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (user_id, json.dumps(merged)),
        )


def get_portfolio_state(user_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT cash, positions_json, trade_log_json, equity_curve_json, realized_json FROM portfolios WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "cash": row["cash"],
        "positions": json.loads(row["positions_json"] or "[]"),
        "trade_log": json.loads(row["trade_log_json"] or "[]"),
        "equity_curve": json.loads(row["equity_curve_json"] or "[]"),
        "realized": json.loads(row["realized_json"] or "{}"),
    }


def save_portfolio_state(user_id: str, cash: float, positions: list, trade_log: list, equity_curve: list, realized: dict):
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

    with get_cursor() as cur:
        cur.execute(
            """INSERT OR REPLACE INTO portfolios
               (user_id, cash, positions_json, trade_log_json, equity_curve_json, realized_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                user_id,
                float(cash),
                json.dumps(positions_data),
                json.dumps(trade_log or []),
                json.dumps(equity_curve or []),
                json.dumps(realized_serializable),
            ),
        )


def get_strategies(user_id: str) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT id, name, code, created_at FROM strategies WHERE user_id = ? ORDER BY id", (user_id,))
        rows = cur.fetchall()
    return [{"id": r["id"], "name": r["name"], "code": r["code"], "created_at": r["created_at"]} for r in rows]


def create_strategy(user_id: str, name: str, code: str) -> dict:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO strategies (user_id, name, code) VALUES (?, ?, ?)",
            (user_id, name, code),
        )
        sid = cur.lastrowid
    return {"id": sid, "name": name, "code": code}


def update_strategy(user_id: str, strategy_id: int, name: Optional[str], code: Optional[str]) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT id, name, code FROM strategies WHERE id = ? AND user_id = ?", (strategy_id, user_id))
        row = cur.fetchone()
    if not row:
        return None
    new_name = name if name is not None else row["name"]
    new_code = code if code is not None else row["code"]
    with get_cursor() as cur:
        cur.execute("UPDATE strategies SET name = ?, code = ? WHERE id = ? AND user_id = ?", (new_name, new_code, strategy_id, user_id))
    return {"id": strategy_id, "name": new_name, "code": new_code}


def delete_strategy(user_id: str, strategy_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("DELETE FROM strategies WHERE id = ? AND user_id = ?", (strategy_id, user_id))
        return cur.rowcount > 0


def get_strategy(user_id: str, strategy_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT id, name, code FROM strategies WHERE id = ? AND user_id = ?", (strategy_id, user_id))
        row = cur.fetchone()
    return dict(row) if row else None


def save_run(user_id: str, run_data: dict) -> int:
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO runs (user_id, strategy_id, strategy_name, symbols_json, start_date, end_date,
               results_json, portfolio_json, metrics_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                run_data["strategy_id"],
                run_data["strategy"],
                json.dumps(run_data.get("symbols", [])),
                run_data["start_date"],
                run_data["end_date"],
                json.dumps(run_data.get("results", [])),
                json.dumps(run_data.get("portfolio", {})),
                json.dumps(run_data.get("metrics", {})),
            ),
        )
        return cur.lastrowid


def get_runs(user_id: str, limit: int = 25) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, strategy_id, strategy_name, symbols_json, start_date, end_date,
                      results_json, portfolio_json, metrics_json, created_at
               FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        metrics = json.loads(r["metrics_json"] or "{}")
        equity = metrics.get("equity", {})
        trades = metrics.get("trades", {})
        out.append({
            "id": r["id"],
            "created_at": r["created_at"],
            "strategy": r["strategy_name"],
            "strategy_id": r["strategy_id"],
            "symbols": json.loads(r["symbols_json"] or "[]"),
            "start_date": r["start_date"],
            "end_date": r["end_date"],
            "start_value": equity.get("start_value"),
            "end_value": equity.get("end_value"),
            "pnl": equity.get("pnl"),
            "total_return_pct": equity.get("total_return_pct"),
            "max_drawdown_pct": equity.get("max_drawdown_pct"),
            "trades": trades.get("trades"),
            "exits": trades.get("exits"),
            "win_rate_pct": trades.get("win_rate_pct"),
        })
    return out


def get_run(user_id: str, run_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, strategy_id, strategy_name, symbols_json, start_date, end_date,
                      results_json, portfolio_json, metrics_json, created_at
               FROM runs WHERE id = ? AND user_id = ?""",
            (run_id, user_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "started_at": row["created_at"],
        "ended_at": row["created_at"],
        "strategy_id": row["strategy_id"],
        "strategy": row["strategy_name"],
        "symbols": json.loads(row["symbols_json"] or "[]"),
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "results": json.loads(row["results_json"] or "[]"),
        "portfolio": json.loads(row["portfolio_json"] or "{}"),
        "metrics": json.loads(row["metrics_json"] or "{}"),
    }


def clear_runs(user_id: str):
    with get_cursor() as cur:
        cur.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
