"""Monte Carlo simulation: samples from historical returns and runs strategy on many possible paths"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backtest import Backtest, create_strategy_from_code
from portfolio import Portfolio
from stock import Stock

logger = logging.getLogger(__name__)


def _extract_returns(stock: Stock) -> np.ndarray:
    """Extract close-to-close returns from stock history."""
    close = stock.df["Close"]
    returns = close.pct_change().dropna()
    return returns.values.astype(float)


def _build_synthetic_ohlc(
    start_price: float,
    returns: np.ndarray,
    horizon: int,
    seed: int | None = None,
) -> pd.DataFrame:
    """Build synthetic OHLC path by sampling returns with replacement."""
    rng = np.random.default_rng(seed)
    n = len(returns)
    if n == 0:
        raise ValueError("No historical returns to sample from")

    sampled = rng.choice(returns, size=horizon, replace=True)
    dates = pd.date_range(
        start=datetime.now().strftime("%Y-%m-%d"),
        periods=horizon,
        freq="B",
    )

    opens = []
    highs = []
    lows = []
    closes = []
    prev_close = start_price

    for r in sampled:
        open_p = prev_close
        close_p = open_p * (1.0 + r)
        # Simple range: sample from historical volatility if available
        range_pct = abs(r) * 2 + 0.001
        high_p = max(open_p, close_p) * (1.0 + range_pct * 0.5)
        low_p = min(open_p, close_p) * (1.0 - range_pct * 0.5)
        if low_p > high_p:
            low_p, high_p = high_p, low_p
        if close_p > high_p:
            high_p = close_p
        if close_p < low_p:
            low_p = close_p

        opens.append(open_p)
        highs.append(high_p)
        lows.append(low_p)
        closes.append(close_p)
        prev_close = close_p

    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes},
        index=dates,
    )
    df.index.name = "Date"
    return df


def run_montecarlo(
    stock: Stock,
    strategy_code: str,
    settings: dict,
    n_sims: int = 100,
    horizon: int = 252,
    block_lookahead: bool = True,
) -> dict:
    """
    Run Monte Carlo simulation: bootstrap sample from stock's historical returns,
    build synthetic price paths, run strategy on each, return distribution of outcomes.
    """
    returns = _extract_returns(stock)
    if len(returns) < 10:
        raise ValueError("Need at least 10 historical returns for Monte Carlo")

    start_price = float(stock.df["Close"].iloc[-1])
    initial_cash = float(settings.get("initial_cash", 100000))
    cash_per_sim = initial_cash

    end_values = []
    equity_by_day: list[list[float]] = []  # per sim: [v0, v1, ..., v_horizon]
    errors = 0

    for i in range(n_sims):
        try:
            df = _build_synthetic_ohlc(start_price, returns, horizon, seed=i)
            synthetic_stock = Stock(symbol=stock.symbol, df=df)

            port = Portfolio()
            port.add_cash(cash_per_sim)
            port.set_slippage(settings.get("slippage", 0.0) or 0.0)
            port.set_share_min_pct(settings.get("share_min_pct", 10))
            port.set_commission(settings.get("commission", 0.0) or 0.0)
            port.set_commission_per_order(settings.get("commission_per_order", 0.0) or 0.0)
            port.set_commission_per_share(settings.get("commission_per_share", 0.0) or 0.0)
            port.set_allow_short(bool(settings.get("allow_short", True)))
            port.set_short_margin_requirement(settings.get("short_margin_requirement", 1.5) or 1.5)
            port.set_constraints(
                max_positions=settings.get("max_positions", 0) or 0,
                max_position_pct=settings.get("max_position_pct", 0.0) or 0.0,
                min_cash_reserve_pct=settings.get("min_cash_reserve_pct", 0.0) or 0.0,
                min_trade_value=settings.get("min_trade_value", 0.0) or 0.0,
                max_trade_value=settings.get("max_trade_value", 0.0) or 0.0,
                max_order_qty=settings.get("max_order_qty", 0) or 0,
            )

            strategy_obj = create_strategy_from_code(
                synthetic_stock, port, strategy_code, block_lookahead=block_lookahead
            )
            bt = Backtest(strategy_obj, port)
            first_date = df.index[0].strftime("%Y-%m-%d")
            last_date = df.index[-1].strftime("%Y-%m-%d")

            curve: list[float] = []

            def on_bar(idx: int, val: float):
                curve.append(val)

            bt.run(first_date, last_date, on_bar=on_bar)
            if curve:
                equity_by_day.append(curve)
            end_val = float(port.get_value())
            end_values.append(end_val)
        except Exception as e:
            logger.debug("Monte Carlo sim %d failed: %s", i, e)
            errors += 1

    # Build fan chart data: percentiles at each day (include day 0 = initial)
    fan_data: list[dict] = []
    if equity_by_day:
        n_days = min(len(c) for c in equity_by_day)
        dates = pd.date_range(
            start=datetime.now().strftime("%Y-%m-%d"),
            periods=n_days + 1,
            freq="B",
        )
        fan_data.append({
            "day": 0,
            "date": dates[0].strftime("%Y-%m-%d"),
            "p5": initial_cash,
            "p25": initial_cash,
            "p50": initial_cash,
            "p75": initial_cash,
            "p95": initial_cash,
        })
        for d in range(n_days):
            vals = [c[d] for c in equity_by_day if d < len(c)]
            if vals:
                fan_data.append({
                    "day": d + 1,
                    "date": dates[d + 1].strftime("%Y-%m-%d") if d + 1 < len(dates) else dates[-1].strftime("%Y-%m-%d"),
                    "p5": float(np.percentile(vals, 5)),
                    "p25": float(np.percentile(vals, 25)),
                    "p50": float(np.percentile(vals, 50)),
                    "p75": float(np.percentile(vals, 75)),
                    "p95": float(np.percentile(vals, 95)),
                })

    arr = np.array(end_values)
    p5 = float(np.percentile(arr, 5)) if len(arr) > 0 else initial_cash
    p25 = float(np.percentile(arr, 25)) if len(arr) > 0 else initial_cash
    p50 = float(np.percentile(arr, 50)) if len(arr) > 0 else initial_cash
    p75 = float(np.percentile(arr, 75)) if len(arr) > 0 else initial_cash
    p95 = float(np.percentile(arr, 95)) if len(arr) > 0 else initial_cash
    mean_val = float(np.mean(arr)) if len(arr) > 0 else initial_cash
    prob_profit = float(np.mean(arr >= initial_cash)) * 100 if len(arr) > 0 else 0.0

    return {
        "n_sims": n_sims,
        "n_success": len(end_values),
        "n_errors": errors,
        "horizon": horizon,
        "initial_cash": initial_cash,
        "start_price": start_price,
        "percentiles": {"p5": p5, "p25": p25, "p50": p50, "p75": p75, "p95": p95},
        "mean": mean_val,
        "prob_profit_pct": prob_profit,
        "end_values": end_values,
        "fan_data": fan_data,
    }
