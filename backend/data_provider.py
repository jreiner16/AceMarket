"""Fetch market data via yfinance. If you want to switch API provider, you should be able to get away with just changing this file."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def get_ohlc(
    symbol: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch daily OHLC from Yahoo Finance."""
    symbol = symbol.upper().strip()
    to_date = to_date or datetime.now().strftime("%Y-%m-%d")
    from_date = from_date or (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")

    df = yf.download(
        symbol,
        start=from_date,
        end=to_date,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()
    out = df[required].copy()
    out["Volume"] = df["Volume"] if "Volume" in df.columns else 0
    out.index = pd.to_datetime(out.index)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out.index.name = "Date"
    out = out.dropna(subset=required)

    # OHLC sanity validation: High >= Low, Open/Close within [Low, High], positive values
    mask = (
        (out["High"] >= out["Low"])
        & (out["Open"] >= out["Low"])
        & (out["Open"] <= out["High"])
        & (out["Close"] >= out["Low"])
        & (out["Close"] <= out["High"])
        & (out[required].gt(0).all(axis=1))
    )
    invalid_count = (~mask).sum()
    if invalid_count > 0:
        logger.warning("Dropped %d invalid OHLC rows for %s (High<Low or O/C outside range or non-positive)", invalid_count, symbol)
        out = out[mask]
    return out


def search_tickers(query: str, limit: int = 10) -> list[dict]:
    """Search tickers via Yahoo Finance."""
    if len((query or "").strip()) < 2:
        return []
    try:
        if hasattr(yf, "Search"):
            search = yf.Search(query.strip(), max_results=limit)
            quotes = getattr(search, "quotes", None) or []
            out: list[dict] = []
            for q in quotes:
                if isinstance(q, dict):
                    sym = (q.get("symbol") or q.get("ticker") or "").strip()
                    name = (q.get("shortname") or q.get("longname") or "").strip()
                    qtype = (q.get("quoteType") or q.get("type") or "EQUITY") or "EQUITY"
                else:
                    sym = (getattr(q, "symbol", "") or getattr(q, "ticker", "") or "").strip()
                    name = (getattr(q, "shortname", "") or getattr(q, "longname", "") or "").strip()
                    qtype = (getattr(q, "quoteType", "") or getattr(q, "type", "") or "EQUITY") or "EQUITY"
                if sym:
                    out.append({"symbol": sym, "name": name or sym, "type": qtype})
            if out:
                return out[:limit]

        # Only fall back to direct ticker lookup when query looks like a ticker.
        qsym = query.strip().upper()
        if " " in qsym or len(qsym) > 12:
            return []
        ticker = yf.Ticker(qsym)
        info = ticker.info
        if info and info.get("symbol"):
            return [{"symbol": info.get("symbol"), "name": info.get("shortName", info.get("symbol")), "type": info.get("quoteType", "EQUITY")}]
    except Exception:
        pass
    return []
