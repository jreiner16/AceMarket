"""AceMarket API — built with FastAPI server, has auth, persistence, and rate limiting"""
import hashlib
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from contextlib import asynccontextmanager
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from pydantic import BaseModel

from analytics import compute_report


def _json_default(o: Any) -> Any:
    """Handle numpy/pandas/datetime for json.dumps."""
    if hasattr(o, "item") and callable(getattr(o, "item")):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _to_native(obj: Any) -> Any:
    """Round-trip through JSON to guarantee native types only. Bulletproof."""
    return json.loads(json.dumps(obj, default=_json_default))
from backtest import Backtest, create_strategy_from_code
from portfolio import Portfolio
from stock import Stock, make_minimal_stock

logger = logging.getLogger(__name__)

from config import (
    CORS_ORIGINS,
    DATE_STR_MAX_LEN,
    DISABLE_AUTH,
    IS_PRODUCTION,
    MAX_BACKTEST_SYMBOLS,
    MAX_INITIAL_CASH,
    MAX_ORDER_QUANTITY,
    MAX_RUNS_PER_USER,
    MAX_WATCHLIST_QUOTES_SYMBOLS,
    RATE_LIMIT_GENERAL_MAX,
    RATE_LIMIT_GENERAL_WINDOW_SEC,
    RATE_LIMIT_STRATEGY_MAX,
    RATE_LIMIT_STRATEGY_WINDOW_SEC,
    SEARCH_QUERY_MAX_LEN,
    STOCK_CACHE_MAX,
    STOCK_CACHE_TTL_SEC,
    STRATEGY_CODE_MAX_LEN,
    STRATEGY_NAME_MAX_LEN,
    SYMBOL_ALLOWED_CHARS,
    SYMBOL_MAX_LEN,
)

import db
from auth import verify_token

if DISABLE_AUTH:
    logger.warning("DISABLE_AUTH is set — authentication is bypassed (development only).")


# Rate limiting: in-memory per process (use Redis for multi-worker production)
_rate_limit_store: dict[str, list[float]] = {}

# Monte Carlo background jobs: job_id -> { status, result?, error? }
_montecarlo_jobs: dict[str, dict] = {}

# Backtest background jobs: job_id -> { status, result?, error? }
_backtest_jobs: dict[str, dict] = {}


def _check_rate_limit(key: str, window: int, max_calls: int) -> None:
    now = time.time()
    if key not in _rate_limit_store:
        _rate_limit_store[key] = []
    times = _rate_limit_store[key]
    times[:] = [t for t in times if now - t < window]
    if len(times) >= max_calls:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    times.append(now)


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    logger.info("AceMarket API started. Auth: %s", "disabled" if DISABLE_AUTH else "enabled")
    yield
    db.close_conn()
    logger.info("AceMarket API shutdown complete")


app = FastAPI(
    title="AceMarket API",
    description="Paper trading platform with strategy backtesting",
    version="1.0.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    lifespan=lifespan,
)

# CORS: never allow * with credentials. In production, no fallback (empty = no origins).
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        CORS_ORIGINS
        if CORS_ORIGINS
        else ([] if IS_PRODUCTION else ["http://localhost:5173", "http://127.0.0.1:5173"])
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_RATE_LIMIT_SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """General rate limit for API routes (by auth token or IP). When auth is disabled, use IP only to prevent bypass."""
    path = request.url.path.rstrip("/")
    if path in _RATE_LIMIT_SKIP_PATHS or not path.startswith("/api"):
        return await call_next(request)
    ip = request.client.host if request.client else "unknown"
    if DISABLE_AUTH:
        key = f"general:ip:{ip}"
    else:
        auth = request.headers.get("Authorization") or ""
        if auth:
            key = f"general:{hashlib.sha256(auth.encode()).hexdigest()}"
        else:
            key = f"general:ip:{ip}"
    try:
        _check_rate_limit(key, RATE_LIMIT_GENERAL_WINDOW_SEC, RATE_LIMIT_GENERAL_MAX)
    except HTTPException:
        raise
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


# In-memory stock cache (shared across users)
_stock_cache: dict[str, dict] = {}
_stock_cache_lock = Lock()

# Chart response cache: key -> {ts, data}. TTL 5 min.
_chart_cache: dict[str, dict] = {}
_chart_cache_lock = Lock()
CHART_CACHE_TTL = 300
CHART_CACHE_MAX = 32


def _validate_symbol(symbol: str) -> str:
    """Validate and normalize symbol. Raises HTTPException if invalid."""
    s = (symbol or "").strip().upper()
    if not s:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")
    if len(s) > SYMBOL_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"Symbol too long (max {SYMBOL_MAX_LEN})")
    if not all(c in SYMBOL_ALLOWED_CHARS for c in s):
        raise HTTPException(status_code=400, detail="Symbol contains invalid characters")
    return s


def _validate_date_str(value: Optional[str]) -> Optional[str]:
    """Validate date string (YYYY-MM-DD), max length. Returns normalized string or None. Raises HTTPException if invalid."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = (value or "").strip()
    if len(s) > DATE_STR_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"Date string too long (max {DATE_STR_MAX_LEN} chars)")
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")
    try:
        int(s[:4])
        int(s[5:7])
        int(s[8:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")
    return s


def _safe_error_message(e: Exception) -> str:
    """Return user-safe error message; log full detail in production."""
    msg = str(e)
    if IS_PRODUCTION:
        logger.warning("Sanitized error response: %s", msg)
        return "Operation failed. Please try again or contact support."
    return msg


def get_stock(symbol: str) -> Stock:
    symbol = _validate_symbol(symbol)
    now = time.time()
    with _stock_cache_lock:
        expired = [k for k, v in _stock_cache.items() if now - float(v.get("ts", 0)) > STOCK_CACHE_TTL_SEC]
        for k in expired:
            _stock_cache.pop(k, None)

        if symbol not in _stock_cache:
            stock = Stock(symbol)
            if stock.df.empty:
                raise HTTPException(status_code=404, detail=f"No data for {symbol}")
            _stock_cache[symbol] = {"ts": now, "stock": stock}
            if len(_stock_cache) > STOCK_CACHE_MAX:
                lru = min(_stock_cache.items(), key=lambda kv: float(kv[1].get("ts", 0)))[0]
                if lru != symbol:
                    _stock_cache.pop(lru, None)
            _stock_cache[symbol]["ts"] = now
            return _stock_cache[symbol]["stock"]
        _stock_cache[symbol]["ts"] = now
        return _stock_cache[symbol]["stock"]


def get_portfolio(user_id: str) -> Portfolio:
    """Load or create portfolio for user. Applies settings from db."""
    settings = db.get_settings(user_id)

    def _get_stock(sym: str) -> Stock:
        return get_stock(sym)

    port = Portfolio()
    state = db.get_portfolio_state(user_id)
    if state:
        # Prefetch all position stocks in parallel (was sequential, now ~5x faster)
        symbols = [str(p.get("symbol", "")).upper() for p in state.get("positions", []) if p.get("symbol")]
        if symbols:
            max_w = min(8, len(symbols))
            with ThreadPoolExecutor(max_workers=max_w) as ex:
                futures = {ex.submit(get_stock, s): s for s in symbols}
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception:
                        pass
        port.restore_from_state(
            cash=state["cash"],
            positions_data=state["positions"],
            trade_log=state["trade_log"],
            equity_curve=state["equity_curve"],
            realized=state.get("realized", {}),
            get_stock=_get_stock,
        )
    else:
        port.add_cash(settings["initial_cash"])

    port.set_slippage(settings.get("slippage", 0.0) or 0.0)
    port.set_share_min_pct(settings.get("share_min_pct", 10))
    port.set_commission(settings.get("commission", 0.0) or 0.0)
    port.set_commission_per_order(settings.get("commission_per_order", 0.0) or 0.0)
    port.set_commission_per_share(settings.get("commission_per_share", 0.0) or 0.0)
    port.set_allow_short(bool(settings.get("allow_short", True)))
    port.set_short_margin_requirement(settings.get("short_margin_requirement", 1.5) or 1.5)
    _apply_portfolio_constraints(port, settings)
    return port


def _apply_portfolio_constraints(port: Portfolio, settings: dict) -> None:
    """Apply risk/constraint settings to a portfolio instance."""
    port.set_constraints(
        max_positions=settings.get("max_positions", 0) or 0,
        max_position_pct=settings.get("max_position_pct", 0.0) or 0.0,
        min_cash_reserve_pct=settings.get("min_cash_reserve_pct", 0.0) or 0.0,
        min_trade_value=settings.get("min_trade_value", 0.0) or 0.0,
        max_trade_value=settings.get("max_trade_value", 0.0) or 0.0,
        max_order_qty=settings.get("max_order_qty", 0) or 0,
    )


def _run_backtest_single_symbol(
    symbol: str,
    strat: dict,
    settings: dict,
    cash_per_symbol: float,
    start_date: str,
    end_date: str,
    train_end: Optional[str],
    test_start: Optional[str],
    auto_liquidate: bool,
) -> dict:
    """Run backtest for one symbol. Returns result dict or error."""
    try:
        port = Portfolio()
        port.add_cash(cash_per_symbol)
        port.set_slippage(settings.get("slippage", 0.0) or 0.0)
        port.set_share_min_pct(settings.get("share_min_pct", 10))
        port.set_commission(settings.get("commission", 0.0) or 0.0)
        port.set_commission_per_order(settings.get("commission_per_order", 0.0) or 0.0)
        port.set_commission_per_share(settings.get("commission_per_share", 0.0) or 0.0)
        port.set_allow_short(bool(settings.get("allow_short", True)))
        port.set_short_margin_requirement(settings.get("short_margin_requirement", 1.5) or 1.5)
        _apply_portfolio_constraints(port, settings)
        port.fill_at_next_open = True
        port.record_equity_per_bar = True

        stock = get_stock(symbol)
        block_lookahead = bool(settings.get("block_lookahead", True))
        strategy_obj = create_strategy_from_code(stock, port, strat["code"], block_lookahead=block_lookahead)
        bt = Backtest(strategy_obj, port)

        if train_end and test_start:
            bt.run(start_date, train_end)
            train_val = float(port.get_value(stock.to_iloc(train_end)))
            train_ec = list(port.equity_curve or [])
            train_tl = list(port.trade_log or [])
            train_metrics = compute_report(
                trade_log=train_tl,
                equity_curve=[{"i": 0, "v": cash_per_symbol, "time": start_date}] + train_ec,
                initial_cash=cash_per_symbol,
            )
            port = Portfolio()
            port.add_cash(cash_per_symbol)
            port.set_slippage(settings.get("slippage", 0.0) or 0.0)
            port.set_share_min_pct(settings.get("share_min_pct", 10))
            port.set_commission(settings.get("commission", 0.0) or 0.0)
            port.set_commission_per_order(settings.get("commission_per_order", 0.0) or 0.0)
            port.set_commission_per_share(settings.get("commission_per_share", 0.0) or 0.0)
            port.set_allow_short(bool(settings.get("allow_short", True)))
            port.set_short_margin_requirement(settings.get("short_margin_requirement", 1.5) or 1.5)
            _apply_portfolio_constraints(port, settings)
            port.fill_at_next_open = True
            port.record_equity_per_bar = True
            strategy_obj = create_strategy_from_code(stock, port, strat["code"], block_lookahead=block_lookahead)
            bt = Backtest(strategy_obj, port)
            bt.run(test_start, end_date)
            test_ec = list(port.equity_curve or [])
            test_tl = list(port.trade_log or [])
            test_metrics = compute_report(
                trade_log=test_tl,
                equity_curve=[{"i": 0, "v": cash_per_symbol, "time": test_start}] + test_ec,
                initial_cash=cash_per_symbol,
            )
        else:
            bt.run(start_date, end_date)
            train_metrics = None
            test_metrics = None

        if auto_liquidate:
            pos = port.get_position(stock)
            if pos is not None:
                qty0 = float(pos.get("quantity") or 0)
                if qty0 != 0:
                    end_iloc = stock.to_iloc(end_date)
                    port.exit_position(stock, abs(qty0), end_iloc)

        end_iloc = stock.to_iloc(end_date)
        end_val = float(port.get_value(end_iloc))
        return {
            "ok": True,
            "symbol": symbol,
            "end_val": end_val,
            "equity_curve": list(port.equity_curve or []),
            "trade_log": list(port.trade_log or []),
            "train_metrics": train_metrics if train_end else None,
            "test_metrics": test_metrics if test_start else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Strategy run failed for %s: %s", symbol, e)
        return {"ok": False, "symbol": symbol, "error": _safe_error_message(e)}


def save_portfolio(user_id: str, port: Portfolio, settings: dict):
    """Persist portfolio state to db."""
    db.save_portfolio_state(
        user_id=user_id,
        cash=port.cash,
        positions=port.positions(),
        trade_log=port.trade_log,
        equity_curve=port.equity_curve,
        realized=port._realized,
    )


# --- Request/Response models ---
class SearchResult(BaseModel):
    symbol: str
    name: str
    type: str


class Candle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float


class Position(BaseModel):
    symbol: str
    quantity: float
    side: str
    avg_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    realized_pnl: float = 0.0


class OpenPositionRequest(BaseModel):
    symbol: str
    quantity: float
    side: str


class ClosePositionRequest(BaseModel):
    symbol: str
    quantity: float


class SettingsUpdate(BaseModel):
    initial_cash: Optional[float] = None
    slippage: Optional[float] = None
    share_min_pct: Optional[float] = None
    commission: Optional[float] = None
    commission_per_order: Optional[float] = None
    commission_per_share: Optional[float] = None
    allow_short: Optional[bool] = None
    max_positions: Optional[int] = None
    max_position_pct: Optional[float] = None
    min_cash_reserve_pct: Optional[float] = None
    min_trade_value: Optional[float] = None
    max_trade_value: Optional[float] = None
    max_order_qty: Optional[int] = None
    short_margin_requirement: Optional[float] = None
    auto_liquidate_end: Optional[bool] = None
    block_lookahead: Optional[bool] = None


class WatchlistUpdate(BaseModel):
    watchlist: list[str]


class StrategyCreate(BaseModel):
    name: str
    code: str


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


class RunStrategyRequest(BaseModel):
    strategy_id: str
    symbols: list[str]
    start_date: str
    end_date: str
    train_pct: Optional[float] = None  # 0 < x < 1: walk-forward, train on first x, test on rest


class MonteCarloRequest(BaseModel):
    strategy_id: str
    symbol: str
    n_sims: int = 100
    horizon: int = 252  # trading days to simulate


# --- Endpoints ---

@app.get("/health")
def health():
    """Health check for load balancers and monitoring."""
    return {"status": "ok", "service": "acemarket-api"}


@app.get("/api/v1/search")
def search_stocks(q: str, user_id: str = Depends(verify_token)):
    """Search for stocks via Yahoo Finance."""
    q = (q or "").strip()
    if q and len(q) > SEARCH_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"Search query too long (max {SEARCH_QUERY_MAX_LEN} characters)")
    from data_provider import search_tickers
    results = search_tickers(q, limit=10)
    return [SearchResult(symbol=r["symbol"], name=r["name"], type=r.get("type", "EQUITY")) for r in results]


@app.get("/api/v1/stock/{symbol}")
def get_stock_data(
    symbol: str,
    user_id: str = Depends(verify_token),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(5000, ge=1, le=10000),
) -> dict:
    """Get OHLC data for charting. Cached 5 min to avoid repeated Yahoo fetches."""
    symbol = _validate_symbol(symbol)
    start_date = _validate_date_str(start_date) if start_date else None
    end_date = _validate_date_str(end_date) if end_date else None
    cache_key = f"{symbol}|{start_date or ''}|{end_date or ''}|{limit}"
    now = time.time()
    with _chart_cache_lock:
        if cache_key in _chart_cache:
            entry = _chart_cache[cache_key]
            if now - float(entry.get("ts", 0)) < CHART_CACHE_TTL:
                return entry["data"]
        expired = [k for k, v in _chart_cache.items() if now - float(v.get("ts", 0)) > CHART_CACHE_TTL]
        for k in expired:
            _chart_cache.pop(k, None)

    stock = Stock(symbol, start_date=start_date, end_date=end_date)
    df = stock.df
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    df = df.tail(limit)

    times = [idx.isoformat()[:10] for idx in df.index]
    opens = df["Open"].astype(float).tolist()
    highs = df["High"].astype(float).tolist()
    lows = df["Low"].astype(float).tolist()
    closes = df["Close"].astype(float).tolist()
    candles = [Candle(time=t, open=o, high=h, low=l, close=c) for t, o, h, l, c in zip(times, opens, highs, lows, closes)]
    data = {
        "symbol": stock.symbol,
        "candles": candles,
        "sma": stock.sma(14)[-len(candles):],
        "ema": stock.ema(14)[-len(candles):],
        "rsi": stock.rsi(14)[-len(candles):],
    }
    with _chart_cache_lock:
        if len(_chart_cache) >= CHART_CACHE_MAX:
            lru = min(_chart_cache.items(), key=lambda kv: float(kv[1].get("ts", 0)))[0]
            _chart_cache.pop(lru, None)
        _chart_cache[cache_key] = {"ts": now, "data": data}
    return data


@app.get("/api/v1/stock/{symbol}/price")
def get_stock_price(symbol: str, user_id: str = Depends(verify_token)) -> dict:
    """Get current (latest) price."""
    stock = get_stock(symbol)
    return {"symbol": symbol, "price": float(stock.price())}


@app.get("/api/v1/bootstrap")
def bootstrap_endpoint(user_id: str = Depends(verify_token)) -> dict:
    """Light bootstrap: runs + watchlist only. Returns in <500ms. Fetch /portfolio in parallel for full data."""
    settings = db.get_settings(user_id)
    watchlist = settings.get("watchlist", ["AAPL", "MSFT", "GOOGL", "TSLA"])
    runs = db.get_runs(user_id, limit=MAX_RUNS_PER_USER)
    return {"runs": runs, "watchlist": watchlist}


@app.get("/api/v1/watchlist")
def get_watchlist(user_id: str = Depends(verify_token)) -> dict:
    """Get user's watchlist symbols."""
    settings = db.get_settings(user_id)
    return {"watchlist": settings.get("watchlist", ["AAPL", "MSFT", "GOOGL", "TSLA"])}


@app.put("/api/v1/watchlist")
def update_watchlist(req: WatchlistUpdate, user_id: str = Depends(verify_token)) -> dict:
    """Save user's watchlist. All symbols must be valid (alphanumeric, dot, hyphen; max 12 chars)."""
    validated = []
    for s in (req.watchlist or [])[:30]:
        if not s:
            continue
        try:
            validated.append(_validate_symbol(str(s).strip()))
        except HTTPException:
            raise
    settings = db.get_settings(user_id)
    settings["watchlist"] = validated
    db.save_settings(user_id, settings)
    return {"watchlist": validated}


def _get_quote_for_symbol(sym: str) -> dict:
    """Fetch quote for one symbol. Used by parallel quote fetcher."""
    try:
        stock = get_stock(sym)
        price = float(stock.price())
        prev_close = float(stock.df["Close"].iloc[-2]) if len(stock.df) >= 2 else price
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {"symbol": sym, "price": price, "prev_close": prev_close, "change": change, "change_pct": change_pct}
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("Quote failed for %s: %s", sym, e)
        return {"symbol": sym, "price": None, "prev_close": None, "change": None, "change_pct": None}


@app.get("/api/v1/watchlist/quotes")
def get_watchlist_quotes(symbols: str, user_id: str = Depends(verify_token)) -> list[dict]:
    """Get price and change from previous close for each symbol. Fetches in parallel."""
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:MAX_WATCHLIST_QUOTES_SYMBOLS]
    if not syms:
        return []
    result = [None] * len(syms)
    sym_to_idx = {s: i for i, s in enumerate(syms)}
    max_workers = min(8, len(syms))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_get_quote_for_symbol, s): s for s in syms}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                q = fut.result()
                result[sym_to_idx[sym]] = q
            except HTTPException:
                raise
            except Exception:
                result[sym_to_idx[sym]] = {"symbol": sym, "price": None, "prev_close": None, "change": None, "change_pct": None}
    return [r for r in result if r is not None]


@app.get("/api/v1/portfolio")
def get_portfolio_state(user_id: str = Depends(verify_token)) -> dict:
    """Get portfolio positions and value."""
    port = get_portfolio(user_id)
    settings = db.get_settings(user_id)
    initial = settings["initial_cash"]

    positions = []
    for p in port.positions():
        stock = p["stock"]
        quantity = float(p["quantity"])
        symbol = stock.symbol
        price = float(stock.price())
        avg_price = float(p.get("avg_price") or 0.0)
        realized_pnl = float(p.get("realized_pnl") or 0.0)
        if quantity > 0:
            pnl = (price - avg_price) * quantity
        else:
            pnl = (avg_price - price) * abs(quantity)
        pnl_pct = (pnl / (avg_price * abs(quantity)) * 100) if avg_price and abs(quantity) else 0.0
        positions.append(
            Position(
                symbol=symbol,
                quantity=abs(quantity),
                side="long" if quantity > 0 else "short",
                avg_price=avg_price,
                current_price=price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                realized_pnl=realized_pnl,
            )
        )

    value = port.get_value()
    trade_log = port.trade_log
    equity_curve = [{"i": 0, "v": initial}] + port.equity_curve
    if not equity_curve or abs(equity_curve[-1]["v"] - value) > 0.01:
        equity_curve.append({"i": max(1, len(port.trade_log)), "v": value})

    equity_curve_enriched = []
    for pt in equity_curve:
        q = dict(pt)
        i = q.get("i")
        if isinstance(i, int) and i > 0 and i - 1 < len(trade_log):
            q["time"] = trade_log[i - 1].get("time")
        equity_curve_enriched.append(q)

    metrics = compute_report(trade_log=trade_log, equity_curve=equity_curve_enriched, initial_cash=initial)
    # Do not save on read; portfolio is persisted only on mutations (open/close/clear/settings)

    return {
        "cash": port.cash,
        "reserved_cash": port.get_reserved_cash(),
        "buying_power": port.get_buying_power(),
        "short_exposure": port.get_short_market_value(),
        "value": value,
        "positions": positions,
        "trade_log": trade_log,
        "equity_curve": equity_curve_enriched,
        "initial_cash": initial,
        "metrics": metrics,
    }


@app.post("/api/v1/portfolio/position")
def open_position(req: OpenPositionRequest, user_id: str = Depends(verify_token)):
    """Open a long or short position."""
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    if req.quantity > MAX_ORDER_QUANTITY:
        raise HTTPException(status_code=400, detail=f"Quantity exceeds maximum ({MAX_ORDER_QUANTITY:,})")
    if req.side not in ("long", "short"):
        raise HTTPException(status_code=400, detail="Side must be 'long' or 'short'")
    stock = get_stock(req.symbol)
    port = get_portfolio(user_id)
    settings = db.get_settings(user_id)
    try:
        if req.side == "long":
            port.enter_position_long(stock, req.quantity)
        else:
            port.enter_position_short(stock, req.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_safe_error_message(e))
    save_portfolio(user_id, port, settings)
    return {"ok": True, "message": f"Opened {req.side} {req.quantity} {req.symbol}"}


@app.post("/api/v1/portfolio/clear")
def clear_history(user_id: str = Depends(verify_token)):
    """Reset portfolio: clear all positions and trade history."""
    port = get_portfolio(user_id)
    settings = db.get_settings(user_id)
    port.clear_history(settings["initial_cash"])
    save_portfolio(user_id, port, settings)
    return {"ok": True, "message": "History cleared"}


@app.delete("/api/v1/portfolio/position")
@app.post("/api/v1/portfolio/position/close")
def close_position(req: ClosePositionRequest, user_id: str = Depends(verify_token)):
    """Close (part of) a position."""
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    if req.quantity > MAX_ORDER_QUANTITY:
        raise HTTPException(status_code=400, detail=f"Quantity exceeds maximum ({MAX_ORDER_QUANTITY:,})")
    stock = get_stock(req.symbol)
    port = get_portfolio(user_id)
    settings = db.get_settings(user_id)
    try:
        port.exit_position(stock, req.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_safe_error_message(e))
    save_portfolio(user_id, port, settings)
    return {"ok": True, "message": f"Closed {req.quantity} {req.symbol}"}


@app.get("/api/v1/settings")
def get_settings_endpoint(user_id: str = Depends(verify_token)) -> dict:
    return db.get_settings(user_id)


@app.get("/api/v1/strategies")
def get_strategies_endpoint(user_id: str = Depends(verify_token)):
    return {"strategies": db.get_strategies(user_id)}


@app.post("/api/v1/strategies")
def create_strategy_endpoint(req: StrategyCreate, user_id: str = Depends(verify_token)):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Strategy name cannot be empty")
    if len((req.name or "").strip()) > STRATEGY_NAME_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"Strategy name too long (max {STRATEGY_NAME_MAX_LEN} characters)")
    if not req.code or not req.code.strip():
        raise HTTPException(status_code=400, detail="Strategy code cannot be empty")
    if len(req.code) > STRATEGY_CODE_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"Strategy code exceeds maximum length ({STRATEGY_CODE_MAX_LEN})")
    name = req.name.strip()
    existing = next((s for s in db.get_strategies(user_id) if s["name"].lower() == name.lower()), None)
    if existing:
        raise HTTPException(status_code=400, detail=f"Strategy '{name}' already exists")
    settings = db.get_settings(user_id)
    block_lookahead = bool(settings.get("block_lookahead", True))
    try:
        stock = make_minimal_stock("AAPL")
        port = Portfolio()
        port.add_cash(1000)
        create_strategy_from_code(stock, port, req.code, block_lookahead=block_lookahead)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_safe_error_message(e))
    strat = db.create_strategy(user_id, name, req.code)
    return {"ok": True, "strategy": strat}


@app.put("/api/v1/strategies/{strategy_id}")
def update_strategy_endpoint(strategy_id: str, upd: StrategyUpdate, user_id: str = Depends(verify_token)):
    strat = db.get_strategy(user_id, strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if upd.name is not None:
        n = upd.name.strip()
        if not n:
            raise HTTPException(status_code=400, detail="Strategy name cannot be empty")
        if len(n) > STRATEGY_NAME_MAX_LEN:
            raise HTTPException(status_code=400, detail=f"Strategy name too long (max {STRATEGY_NAME_MAX_LEN} characters)")
        other = next((s for s in db.get_strategies(user_id) if s["id"] != strategy_id and s["name"].lower() == n.lower()), None)
        if other:
            raise HTTPException(status_code=400, detail=f"Strategy '{n}' already exists")
    if upd.code is not None and not upd.code.strip():
        raise HTTPException(status_code=400, detail="Strategy code cannot be empty")
    if upd.code is not None and len(upd.code) > STRATEGY_CODE_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"Strategy code exceeds maximum length ({STRATEGY_CODE_MAX_LEN})")
    settings = db.get_settings(user_id)
    block_lookahead = bool(settings.get("block_lookahead", True))
    try:
        stock = make_minimal_stock("AAPL")
        port = Portfolio()
        port.add_cash(1000)
        create_strategy_from_code(stock, port, upd.code if upd.code is not None else strat["code"], block_lookahead=block_lookahead)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_safe_error_message(e))
    updated = db.update_strategy(user_id, strategy_id, upd.name, upd.code)
    return {"ok": True, "strategy": updated}


@app.delete("/api/v1/strategies/{strategy_id}")
def delete_strategy_endpoint(strategy_id: str, user_id: str = Depends(verify_token)):
    if not db.delete_strategy(user_id, strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"ok": True}


def _run_backtest_background(job_id: str, user_id: str, req: RunStrategyRequest):
    """Background task: run backtest and store result. Avoids Render's 30s request timeout."""
    try:
        strat = db.get_strategy(user_id, req.strategy_id)
        if not strat:
            _backtest_jobs[job_id] = {"status": "error", "user_id": user_id, "error": "Strategy not found"}
            return
        symbols = [s.strip().upper() for s in req.symbols if s and s.strip()][:MAX_BACKTEST_SYMBOLS]
        if not symbols:
            _backtest_jobs[job_id] = {"status": "error", "user_id": user_id, "error": "Select at least one stock"}
            return
        settings = db.get_settings(user_id)
        initial_total = float(settings["initial_cash"])
        cash_per_symbol = initial_total / len(symbols)
        train_pct = req.train_pct
        start_d = pd.to_datetime(req.start_date)
        end_d = pd.to_datetime(req.end_date)
        if train_pct and 0 < train_pct < 1:
            delta = (end_d - start_d).days
            split_offset = int(delta * train_pct)
            split_d = start_d + pd.Timedelta(days=split_offset)
            split_date = split_d.strftime("%Y-%m-%d")
            train_end, test_start = split_date, split_date
        else:
            train_end, test_start = None, None
        auto_liquidate = bool(settings.get("auto_liquidate_end", True))
        max_workers = min(8, max(1, len(symbols)))
        symbol_to_result: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {
                ex.submit(
                    _run_backtest_single_symbol,
                    symbol, strat, settings, cash_per_symbol,
                    req.start_date, req.end_date, train_end, test_start, auto_liquidate,
                ): symbol
                for symbol in symbols
            }
            for fut in as_completed(futures):
                symbol = futures[fut]
                try:
                    symbol_to_result[symbol] = fut.result()
                except HTTPException:
                    raise
                except Exception as e:
                    logger.warning("Strategy run failed for %s: %s", symbol, e)
                    symbol_to_result[symbol] = {"ok": False, "symbol": symbol, "error": _safe_error_message(e)}
        results = []
        combined_trade_log = []
        portfolio_equity_curves = []
        total_end_value = 0.0
        train_metrics = None
        test_metrics = None
        for symbol in symbols:
            r = symbol_to_result.get(symbol)
            if not r or not r.get("ok"):
                results.append({"strategy": strat["name"], "symbol": symbol, "error": (r or {}).get("error", "Unknown error")})
                continue
            total_end_value += r["end_val"]
            results.append({"strategy": strat["name"], "symbol": symbol, "start_value": cash_per_symbol, "end_value": r["end_val"], "pnl": r["end_val"] - cash_per_symbol})
            combined_trade_log.extend(r.get("trade_log") or [])
            portfolio_equity_curves.append((r.get("equity_curve") or [], r.get("trade_log") or []))
            if train_end and test_start:
                if train_metrics is None and r.get("train_metrics"):
                    train_metrics = r["train_metrics"]
                if test_metrics is None and r.get("test_metrics"):
                    test_metrics = r["test_metrics"]
        port_value = total_end_value
        initial = initial_total

        def _enrich_equity(ec, tl):
            out = []
            for j, pt in enumerate(ec):
                t = pt.get("time")
                if t is None and j > 0 and j - 1 < len(tl) and tl[j - 1].get("time"):
                    t = tl[j - 1]["time"]
                out.append({"i": pt.get("i", j), "v": pt.get("v"), "time": t})
            return out

        if not portfolio_equity_curves:
            equity_curve_enriched = [{"i": 0, "v": initial, "time": None}, {"i": 1, "v": port_value, "time": req.end_date}]
        elif len(portfolio_equity_curves) == 1:
            ec, tl = portfolio_equity_curves[0]
            equity_curve_enriched = _enrich_equity(ec, tl)
            if equity_curve_enriched:
                if equity_curve_enriched[0].get("i") != 0:
                    equity_curve_enriched.insert(0, {"i": 0, "v": initial, "time": req.start_date})
                if equity_curve_enriched[0].get("time") is None:
                    equity_curve_enriched[0]["time"] = req.start_date
                if equity_curve_enriched[-1].get("time") is None:
                    equity_curve_enriched[-1]["time"] = req.end_date
        else:
            events = []
            for pidx, (ec, tl) in enumerate(portfolio_equity_curves):
                for j, pt in enumerate(ec):
                    t = pt.get("time")
                    if t is None:
                        t = req.start_date if j == 0 else (tl[j - 1]["time"] if j - 1 < len(tl) and tl[j - 1].get("time") else None)
                    if t:
                        events.append((t, pidx, float(pt.get("v") or 0)))
            events.sort(key=lambda x: (x[0], x[1]))
            current = [float(ec[0].get("v") or 0) if ec else 0 for ec, _ in portfolio_equity_curves]
            equity_curve_enriched = [{"i": 0, "v": initial, "time": None}]
            seen_times = set()
            for t, pidx, v in events:
                current[pidx] = v
                if t not in seen_times:
                    seen_times.add(t)
                    equity_curve_enriched.append({"i": len(equity_curve_enriched), "v": sum(current), "time": t})

        metrics = compute_report(trade_log=combined_trade_log, equity_curve=equity_curve_enriched, initial_cash=initial)
        run_data = _to_native({
            "strategy_id": req.strategy_id,
            "strategy": strat["name"],
            "symbols": symbols,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "train_pct": train_pct,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "results": results,
            "portfolio": {"initial_cash": initial, "value": port_value, "trade_log": combined_trade_log, "equity_curve": equity_curve_enriched},
            "metrics": metrics,
        })
        run_id = db.save_run(user_id, run_data)
        result = {"ok": True, "results": results, "run_id": int(run_id)}
        try:
            _backtest_jobs[job_id] = {"status": "done", "user_id": user_id, "result": _to_native(result)}
        except Exception as serr:
            logger.exception("Backtest result serialization failed: %s", serr)
            _backtest_jobs[job_id] = {"status": "error", "user_id": user_id, "error": _safe_error_message(serr)}
    except Exception as e:
        logger.exception("Backtest job %s failed", job_id)
        _backtest_jobs[job_id] = {"status": "error", "user_id": user_id, "error": _safe_error_message(e)}


@app.post("/api/v1/strategies/run")
def run_strategy_endpoint(req: RunStrategyRequest, background_tasks: BackgroundTasks, user_id: str = Depends(verify_token)):
    """Start backtest in background, return job_id immediately. Poll GET /strategies/run/{job_id} for result."""
    _check_rate_limit(f"strategy:{user_id}", RATE_LIMIT_STRATEGY_WINDOW_SEC, RATE_LIMIT_STRATEGY_MAX)
    strat = db.get_strategy(user_id, req.strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if not req.symbols:
        raise HTTPException(status_code=400, detail="Select at least one stock")
    symbols = [s.strip().upper() for s in req.symbols if s and s.strip()][:MAX_BACKTEST_SYMBOLS]
    if not symbols:
        raise HTTPException(status_code=400, detail="Select at least one stock")
    if len([s for s in (req.symbols or []) if s and s.strip()]) > MAX_BACKTEST_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Too many symbols (max {MAX_BACKTEST_SYMBOLS})")
    if not (req.start_date or "").strip():
        raise HTTPException(status_code=400, detail="start_date is required (YYYY-MM-DD)")
    if not (req.end_date or "").strip():
        raise HTTPException(status_code=400, detail="end_date is required (YYYY-MM-DD)")
    _validate_date_str(req.start_date)
    _validate_date_str(req.end_date)
    train_pct = req.train_pct
    if train_pct is not None and (train_pct <= 0 or train_pct >= 1):
        raise HTTPException(status_code=400, detail="train_pct must be between 0 and 1 (exclusive)")
    job_id = str(uuid.uuid4())
    _backtest_jobs[job_id] = {"status": "pending", "user_id": user_id}
    background_tasks.add_task(_run_backtest_background, job_id, user_id, req)
    return {"ok": True, "job_id": job_id}


@app.get("/api/v1/strategies/run/{job_id}")
def backtest_poll_endpoint(job_id: str, user_id: str = Depends(verify_token)):
    """Poll for backtest result. Returns status: pending | done | error."""
    if job_id not in _backtest_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _backtest_jobs[job_id]
    if job.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if job["status"] == "done":
        return job["result"]
    if job["status"] == "error":
        raise HTTPException(status_code=400, detail=job.get("error", "Backtest failed"))
    return {"status": "pending"}


def _run_montecarlo_background(job_id: str, user_id: str, req: MonteCarloRequest):
    """Background task: run Monte Carlo and store result. Avoids Render's 30s request timeout."""
    try:
        strat = db.get_strategy(user_id, req.strategy_id)
        if not strat:
            _montecarlo_jobs[job_id] = {"status": "error", "user_id": user_id, "error": "Strategy not found"}
            return
        symbol = _validate_symbol(req.symbol)
        n_sims = max(10, min(500, req.n_sims))
        horizon = max(21, min(504, req.horizon))
        stock = get_stock(symbol)
        if stock.df.empty:
            _montecarlo_jobs[job_id] = {"status": "error", "user_id": user_id, "error": f"No data for {symbol}"}
            return
        settings = db.get_settings(user_id)
        block_lookahead = bool(settings.get("block_lookahead", True))
        from montecarlo import run_montecarlo
        result = run_montecarlo(
            stock=stock,
            strategy_code=strat["code"],
            settings=settings,
            n_sims=n_sims,
            horizon=horizon,
            block_lookahead=block_lookahead,
        )
        initial = result["initial_cash"]
        mean_val = result["mean"]
        pnl = mean_val - initial
        total_return_pct = (pnl / initial * 100) if initial else 0
        run_data = _to_native({
            "strategy_id": req.strategy_id,
            "strategy": strat["name"] + " (MC)",
            "symbols": [symbol],
            "start_date": "Monte Carlo",
            "end_date": f"{horizon}d",
            "results": [{"symbol": symbol, "start_value": initial, "end_value": mean_val, "pnl": pnl}],
            "portfolio": {
                "run_type": "montecarlo",
                "initial_cash": initial,
                "value": mean_val,
                "fan_data": result.get("fan_data", []),
                "percentiles": result.get("percentiles", {}),
                "n_sims": result.get("n_success", 0),
                "n_errors": result.get("n_errors", 0),
                "horizon": horizon,
                "prob_profit_pct": result.get("prob_profit_pct", 0),
            },
            "metrics": {
                "equity": {"start_value": initial, "end_value": mean_val, "pnl": pnl, "total_return_pct": total_return_pct},
                "trades": {"win_rate_pct": result.get("prob_profit_pct", 0), "trades": 0, "exits": 0},
            },
        })
        run_id = db.save_run(user_id, run_data)
        logger.info("Monte Carlo run saved: id=%s user=%s symbol=%s", run_id, user_id, symbol)
        result_payload = {"ok": True, "strategy": strat["name"], "symbol": symbol, "run_id": int(run_id), **result}
        try:
            _montecarlo_jobs[job_id] = {"status": "done", "user_id": user_id, "result": _to_native(result_payload)}
        except Exception as serr:
            logger.exception("Monte Carlo result serialization failed: %s", serr)
            _montecarlo_jobs[job_id] = {"status": "error", "user_id": user_id, "error": _safe_error_message(serr)}
    except Exception as e:
        logger.exception("Monte Carlo job %s failed", job_id)
        _montecarlo_jobs[job_id] = {"status": "error", "user_id": user_id, "error": _safe_error_message(e)}


@app.post("/api/v1/strategies/montecarlo")
def montecarlo_endpoint(req: MonteCarloRequest, background_tasks: BackgroundTasks, user_id: str = Depends(verify_token)):
    """Start Monte Carlo in background, return job_id immediately. Poll GET /montecarlo/{job_id} for result."""
    _check_rate_limit(f"strategy:{user_id}", RATE_LIMIT_STRATEGY_WINDOW_SEC, RATE_LIMIT_STRATEGY_MAX)
    strat = db.get_strategy(user_id, req.strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    symbol = _validate_symbol(req.symbol)
    stock = get_stock(symbol)
    if stock.df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    job_id = str(uuid.uuid4())
    _montecarlo_jobs[job_id] = {"status": "pending", "user_id": user_id}
    background_tasks.add_task(_run_montecarlo_background, job_id, user_id, req)
    return {"ok": True, "job_id": job_id}


@app.get("/api/v1/strategies/montecarlo/{job_id}")
def montecarlo_poll_endpoint(job_id: str, user_id: str = Depends(verify_token)):
    """Poll for Monte Carlo result. Returns status: pending | done | error."""
    if job_id not in _montecarlo_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _montecarlo_jobs[job_id]
    if job.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if job["status"] == "done":
        return job["result"]
    if job["status"] == "error":
        raise HTTPException(status_code=400, detail=job.get("error", "Monte Carlo failed"))
    return {"status": "pending"}


@app.get("/api/v1/runs")
def list_runs(user_id: str = Depends(verify_token)):
    summaries = db.get_runs(user_id, limit=MAX_RUNS_PER_USER)
    mc_count = sum(1 for s in summaries if s.get("run_type") == "montecarlo")
    logger.info("list_runs: user=%s total=%d montecarlo=%d", user_id, len(summaries), mc_count)
    return {"runs": summaries}


def _reconstruct_equity_curve_from_trades(trade_log: list, initial_cash: float, start_date: str, end_date: str) -> list:
    """Reconstruct equity curve from trade_log when stored curve has only 2 points (legacy runs)."""
    if not trade_log:
        return [{"i": 0, "v": initial_cash, "time": start_date}, {"i": 1, "v": initial_cash, "time": end_date}]
    curve = [{"i": 0, "v": initial_cash, "time": start_date}]
    cash = float(initial_cash)
    position = 0
    for i, t in enumerate(trade_log):
        qty = float(t.get("quantity") or 0)
        price = float(t.get("price") or t.get("fill_price") or 0)
        typ = (t.get("type") or "").lower()
        if typ == "long":
            cost = float(t.get("cost") or 0)
            cash -= cost
            position += qty
        elif typ == "exit":
            amount = float(t.get("amount") or 0)
            cash += amount
            position -= qty
        value = cash + position * price if position else cash
        curve.append({"i": i + 1, "v": value, "time": t.get("time") or end_date})
    return curve


@app.get("/api/v1/runs/{run_id}")
def get_run_endpoint(run_id: int, user_id: str = Depends(verify_token)):
    r = db.get_run(user_id, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    port = r.get("portfolio") or {}
    ec = port.get("equity_curve") or []
    tl = port.get("trade_log") or []
    # Reconstruct equity curve for legacy runs that only stored start/end
    if len(ec) <= 2 and len(tl) > 2:
        initial = float(port.get("initial_cash") or 0)
        ec = _reconstruct_equity_curve_from_trades(tl, initial, r.get("start_date", ""), r.get("end_date", ""))
        port = dict(port)
        port["equity_curve"] = ec
        r = dict(r)
        r["portfolio"] = port
        # Recompute metrics with full curve
        from analytics import compute_report
        r["metrics"] = compute_report(trade_log=tl, equity_curve=ec, initial_cash=initial)
    return {"run": r}


@app.delete("/api/v1/runs")
def clear_runs_endpoint(user_id: str = Depends(verify_token)):
    db.clear_runs(user_id)
    return {"ok": True}


@app.put("/api/v1/settings")
def update_settings_endpoint(upd: SettingsUpdate, user_id: str = Depends(verify_token)):
    settings = db.get_settings(user_id)

    if upd.initial_cash is not None:
        if upd.initial_cash < 0:
            raise HTTPException(status_code=400, detail="initial_cash must be >= 0")
        if upd.initial_cash > MAX_INITIAL_CASH:
            raise HTTPException(status_code=400, detail=f"initial_cash must be <= {MAX_INITIAL_CASH:,.0f}")
        settings["initial_cash"] = float(upd.initial_cash)
        port = get_portfolio(user_id)
        cur = float(port.get_value())
        diff = float(upd.initial_cash) - cur
        if abs(diff) > 0.01:
            port.add_cash(diff)
        save_portfolio(user_id, port, settings)

    if upd.share_min_pct is not None:
        pct = float(upd.share_min_pct)
        if pct <= 0 or pct > 100:
            raise HTTPException(status_code=400, detail="share_min_pct must be 1–100 (e.g. 10 = 0.1 share min)")
        settings["share_min_pct"] = pct
    if upd.slippage is not None:
        if upd.slippage < 0 or upd.slippage >= 1:
            raise HTTPException(status_code=400, detail="slippage must be in [0, 1) as decimal (e.g. 0.001 = 0.1%%)")
        settings["slippage"] = float(upd.slippage)
    if upd.commission is not None:
        if upd.commission < 0 or upd.commission >= 1:
            raise HTTPException(status_code=400, detail="commission must be in [0, 1) as decimal (e.g. 0.001 = 0.1%%)")
        settings["commission"] = float(upd.commission)
    if upd.commission_per_order is not None:
        if upd.commission_per_order < 0:
            raise HTTPException(status_code=400, detail="commission_per_order must be >= 0")
        settings["commission_per_order"] = float(upd.commission_per_order)
    if upd.commission_per_share is not None:
        if upd.commission_per_share < 0:
            raise HTTPException(status_code=400, detail="commission_per_share must be >= 0")
        settings["commission_per_share"] = float(upd.commission_per_share)

    if upd.allow_short is not None:
        settings["allow_short"] = bool(upd.allow_short)
    if upd.max_positions is not None:
        if upd.max_positions < 0:
            raise HTTPException(status_code=400, detail="max_positions must be >= 0")
        settings["max_positions"] = int(upd.max_positions)
    if upd.max_position_pct is not None:
        if upd.max_position_pct < 0 or upd.max_position_pct > 1:
            raise HTTPException(status_code=400, detail="max_position_pct must be in [0, 1]")
        settings["max_position_pct"] = float(upd.max_position_pct)
    if upd.min_cash_reserve_pct is not None:
        if upd.min_cash_reserve_pct < 0 or upd.min_cash_reserve_pct > 1:
            raise HTTPException(status_code=400, detail="min_cash_reserve_pct must be in [0, 1]")
        settings["min_cash_reserve_pct"] = float(upd.min_cash_reserve_pct)
    if upd.min_trade_value is not None:
        if upd.min_trade_value < 0:
            raise HTTPException(status_code=400, detail="min_trade_value must be >= 0")
        settings["min_trade_value"] = float(upd.min_trade_value)
    if upd.max_trade_value is not None:
        if upd.max_trade_value < 0:
            raise HTTPException(status_code=400, detail="max_trade_value must be >= 0")
        settings["max_trade_value"] = float(upd.max_trade_value)
    if upd.max_order_qty is not None:
        if upd.max_order_qty < 0:
            raise HTTPException(status_code=400, detail="max_order_qty must be >= 0")
        settings["max_order_qty"] = int(upd.max_order_qty)
    if upd.short_margin_requirement is not None:
        if upd.short_margin_requirement < 1 or upd.short_margin_requirement > 3:
            raise HTTPException(status_code=400, detail="short_margin_requirement must be in [1, 3]")
        settings["short_margin_requirement"] = float(upd.short_margin_requirement)
    if upd.auto_liquidate_end is not None:
        settings["auto_liquidate_end"] = bool(upd.auto_liquidate_end)
    if upd.block_lookahead is not None:
        settings["block_lookahead"] = bool(upd.block_lookahead)

    if settings.get("max_trade_value", 0.0) and settings.get("min_trade_value", 0.0):
        if float(settings["max_trade_value"]) < float(settings["min_trade_value"]):
            raise HTTPException(status_code=400, detail="max_trade_value must be >= min_trade_value")

    db.save_settings(user_id, settings)
    return {"ok": True, "settings": settings}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
