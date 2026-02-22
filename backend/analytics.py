"""Performance analytics: equity metrics, trade metrics, and risk-adjusted returns."""
from __future__ import annotations

from typing import Any, Iterable

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE_ANNUAL = 0.0  # Configurable; 0 for simplicity


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _pct(x: float) -> float:
    return float(x) * 100.0


def _expand_equity_to_daily(
    equity_curve: Iterable[dict],
    initial_cash: float,
) -> tuple[list[float], list[str | None]]:
    """
    Expand trade-to-trade equity curve to daily series via forward-fill.
    Returns (values, dates) for each trading day.
    """
    import pandas as pd

    points = sorted(
        (p for p in (equity_curve or []) if p.get("v") is not None),
        key=lambda p: (p.get("time") or "1970-01-01", p.get("i", 0)),
    )
    if not points:
        return [float(initial_cash)], [None]

    values = [_safe_float(p.get("v")) for p in points]
    times = [p.get("time") for p in points]

    valid_times = [t for t in times if t and len(str(t)) >= 10]
    if not valid_times:
        return values, times

    try:
        start_d = min(valid_times)[:10]
        end_d = max(valid_times)[:10]
        dates = pd.date_range(start=start_d, end=end_d, freq="B")
        if len(dates) == 0:
            return values, times
        idx = pd.to_datetime([(t or start_d)[:10] for t in times])
        series = pd.Series(values, index=idx)
        series = series[~series.index.duplicated(keep="last")]
        series = series.reindex(dates).ffill().bfill()
        series = series.fillna(initial_cash)
        return series.tolist(), [d.strftime("%Y-%m-%d") for d in dates]
    except Exception:
        return values, times


def compute_equity_metrics(
    equity_curve: Iterable[dict],
    initial_cash: float,
) -> dict:
    """
    Equity curve: iterable of {"i": int, "v": float, "time": str?, ...}.
    Returns summary stats, drawdown, and proper annualized Sharpe/Sortino/Calmar.
    """
    points = list(equity_curve or [])
    values = [_safe_float(p.get("v")) for p in points]

    if not values:
        values = [float(initial_cash)]
        points = [{"i": 0, "v": float(initial_cash)}]

    start_value = float(values[0])
    end_value = float(values[-1])
    pnl = end_value - start_value
    total_return = (pnl / start_value) if start_value else 0.0

    peak = start_value
    max_dd = 0.0
    max_dd_duration = 0
    dd_start = 0
    dd_series = []
    for i, v in enumerate(values):
        if v > peak:
            peak = v
            dd_start = i
        dd = (v - peak) / peak if peak else 0.0
        dd_series.append(dd)
        if dd < max_dd:
            max_dd = dd
            max_dd_duration = i - dd_start

    # Daily returns for proper Sharpe/Sortino
    daily_values, _ = _expand_equity_to_daily(points, initial_cash)
    daily_returns = []
    for i in range(1, len(daily_values)):
        prev, cur = daily_values[i - 1], daily_values[i]
        if prev and prev > 0:
            daily_returns.append((cur / prev) - 1.0)
        else:
            daily_returns.append(0.0)

    n_daily = len(daily_returns)
    avg_daily = sum(daily_returns) / n_daily if n_daily else 0.0
    var_daily = sum((r - avg_daily) ** 2 for r in daily_returns) / (n_daily - 1) if n_daily > 1 else 0.0
    stdev_daily = var_daily ** 0.5

    # Annualized metrics
    rf_daily = RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR
    excess_daily = avg_daily - rf_daily
    sharpe_annual = (excess_daily / stdev_daily * (TRADING_DAYS_PER_YEAR ** 0.5)) if stdev_daily else 0.0

    downside_returns = [r for r in daily_returns if r < 0]
    downside_var = (
        sum(r ** 2 for r in downside_returns) / (len(downside_returns) - 1)
        if len(downside_returns) > 1
        else 0.0
    )
    downside_stdev = downside_var ** 0.5
    sortino_annual = (
        (excess_daily / downside_stdev * (TRADING_DAYS_PER_YEAR ** 0.5))
        if downside_stdev
        else (sharpe_annual if excess_daily >= 0 else 0.0)
    )

    years = n_daily / TRADING_DAYS_PER_YEAR if n_daily else 0.0
    cagr = ((end_value / start_value) ** (1 / years) - 1.0) if years and start_value else 0.0
    calmar_annual = (cagr / abs(max_dd)) if max_dd != 0 else (cagr if cagr else 0.0)

    # Turnover (from trade-to-trade)
    trade_returns = []
    for i in range(1, len(values)):
        prev, cur = values[i - 1], values[i]
        if prev and prev > 0:
            trade_returns.append((cur / prev) - 1.0)
    avg_trade_r = sum(trade_returns) / len(trade_returns) if trade_returns else 0.0
    stdev_trade_r = (
        (sum((r - avg_trade_r) ** 2 for r in trade_returns) / (len(trade_returns) - 1)) ** 0.5
        if len(trade_returns) > 1
        else 0.0
    )
    sharpe_like_trade = (avg_trade_r / stdev_trade_r) if stdev_trade_r else 0.0

    return {
        "start_value": start_value,
        "end_value": end_value,
        "pnl": pnl,
        "total_return": total_return,
        "total_return_pct": _pct(total_return),
        "max_drawdown": float(max_dd),
        "max_drawdown_pct": _pct(max_dd),
        "max_drawdown_duration": max_dd_duration,
        "peak_value": float(max(values)) if values else start_value,
        "low_value": float(min(values)) if values else start_value,
        "points": len(values),
        "sharpe_annual": float(sharpe_annual),
        "sortino_annual": float(sortino_annual),
        "calmar_annual": float(calmar_annual),
        "cagr": float(cagr),
        "trade_to_trade_avg_return": avg_trade_r,
        "trade_to_trade_avg_return_pct": _pct(avg_trade_r),
        "trade_to_trade_stdev_return": stdev_trade_r,
        "trade_to_trade_sharpe_like": sharpe_like_trade,
        "drawdown_series": dd_series,
    }


def compute_trade_metrics(trade_log: Iterable[dict]) -> dict:
    trades = list(trade_log or [])
    exits = [t for t in trades if str(t.get("type", "")).lower() == "exit"]

    realized_exits = [_safe_float(t.get("realized_pnl")) for t in exits]
    wins = [x for x in realized_exits if x > 0]
    losses = [x for x in realized_exits if x < 0]

    gross_profit = float(sum(wins))
    gross_loss = float(sum(losses))
    net_realized = float(sum(realized_exits))
    win_rate = (len(wins) / len(realized_exits)) if realized_exits else 0.0

    profit_factor = None
    if losses:
        denom = abs(sum(losses))
        profit_factor = (gross_profit / denom) if denom else None

    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0

    realized_all = float(sum(_safe_float(t.get("realized_pnl")) for t in trades))

    # Turnover: sum of |trade value| / avg portfolio value
    trade_values = []
    for t in trades:
        cost = _safe_float(t.get("cost"), 0) or _safe_float(t.get("proceeds"), 0) or _safe_float(t.get("amount"), 0)
        if cost:
            trade_values.append(abs(cost))
    turnover = sum(trade_values) if trade_values else 0.0

    return {
        "trades": len(trades),
        "exits": len(exits),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "win_rate_pct": _pct(win_rate),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_realized_exits": net_realized,
        "net_realized_all": realized_all,
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "max_win": float(max(wins)) if wins else 0.0,
        "max_loss": float(min(losses)) if losses else 0.0,
        "profit_factor": profit_factor,
        "turnover": turnover,
    }


def compute_symbol_breakdown(trade_log: Iterable[dict]) -> list[dict]:
    trades = list(trade_log or [])
    by = {}
    for t in trades:
        sym = str(t.get("stock") or "").upper()
        if not sym:
            continue
        rec = by.setdefault(sym, {"symbol": sym, "trades": 0, "exits": 0, "net_realized": 0.0})
        rec["trades"] += 1
        rpnl = _safe_float(t.get("realized_pnl"), 0.0)
        if str(t.get("type", "")).lower() == "exit":
            rec["exits"] += 1
            rec["net_realized"] += rpnl
    out = list(by.values())
    out.sort(key=lambda r: (r["net_realized"], r["symbol"]))
    out.reverse()
    return out


def compute_report(
    trade_log: Iterable[dict],
    equity_curve: Iterable[dict],
    initial_cash: float,
) -> dict:
    equity = compute_equity_metrics(equity_curve, initial_cash)
    trades = compute_trade_metrics(trade_log)
    symbols = compute_symbol_breakdown(trade_log)
    return {"equity": equity, "trades": trades, "symbols": symbols}
