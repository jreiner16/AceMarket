"""Stock data"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from data_provider import get_ohlc

logger = logging.getLogger(__name__)


def _safe_float_for_json(x: float) -> Optional[float]:
    """Convert values for use in JSONs"""
    if pd.isna(x) or (isinstance(x, float) and np.isnan(x)):
        return None
    return float(x)


class Stock:
    def __init__(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        df: Optional[pd.DataFrame] = None,
    ):
        self.symbol = symbol.upper().strip()
        self._tr_cache: Optional[pd.Series] = None

        if df is not None:
            self.df = df.copy()
            self.df.index = pd.to_datetime(self.df.index)
            self.df = self.df.sort_index()
        else:
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365 * 30)).strftime("%Y-%m-%d")

            self.df = get_ohlc(self.symbol, start_date, end_date)
            if self.df.empty:
                logger.warning("No data for %s", self.symbol)
                return

            self.df.index = pd.to_datetime(self.df.index)
            self.df = self.df.sort_index()
            logger.info("Loaded data for %s (%d rows)", self.symbol, len(self.df))

        for col in ["Open", "High", "Low", "Close"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        self.df = self.df.dropna(subset=["Open", "High", "Low", "Close"])

    # Indicators
    def rsi(self, period: int = 14) -> List[Optional[float]]:
        close = self.df["Close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi_series = rsi_series.where(avg_loss > 0, 100.0)
        rsi_series.iloc[:period] = np.nan
        return [_safe_float_for_json(x) for x in rsi_series.tolist()]

    def sma(self, period: int = 14) -> List[Optional[float]]:
        s = self.df["Close"].rolling(window=period).mean()
        return [_safe_float_for_json(x) for x in s.tolist()]

    def ema(self, period: int = 14) -> List[Optional[float]]:
        s = self.df["Close"].ewm(span=period, adjust=False).mean()
        return [_safe_float_for_json(x) for x in s.tolist()]

    def macd(
        self,
        long_period: int = 26,
        short_period: int = 12,
    ) -> List[Optional[float]]:
        short_ema = self.df["Close"].ewm(span=short_period, adjust=False).mean()
        long_ema = self.df["Close"].ewm(span=long_period, adjust=False).mean()
        macd_series = short_ema - long_ema
        macd_series.iloc[:long_period] = np.nan
        return [_safe_float_for_json(x) for x in macd_series.tolist()]

    def bollinger_bands(
        self,
        period: int = 20,
        dev: float = 2,
    ) -> List[Tuple[Optional[float], Optional[float], Optional[float]]]:
        close = self.df["Close"]
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = middle + dev * std
        lower = middle - dev * std
        return [
            (
                _safe_float_for_json(u),
                _safe_float_for_json(m),
                _safe_float_for_json(l),
            )
            for u, m, l in zip(upper.tolist(), middle.tolist(), lower.tolist())
        ]

    def _tr_series(self) -> pd.Series:
        if self._tr_cache is not None:
            return self._tr_cache
        high = self.df["High"]
        low = self.df["Low"]
        prev_close = self.df["Close"].shift(1)
        hl = high - low
        hc = (high - prev_close).abs()
        lc = (low - prev_close).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        tr.iloc[0] = hl.iloc[0]
        self._tr_cache = tr
        return tr

    def tr(self, index: Optional[Union[int, str]] = None) -> float:
        i = self.to_iloc(index)
        if i == 0:
            return float(self.df["High"].iloc[0] - self.df["Low"].iloc[0])
        return float(self._tr_series().iloc[i])

    def atr(self, period: int = 14) -> List[Optional[float]]:
        tr = self._tr_series()
        tr_from_period = pd.concat([
            pd.Series([tr.iloc[1 : period + 1].mean()], index=[tr.index[period]]),
            tr.iloc[period + 1 :],
        ])
        atr_smoothed = tr_from_period.ewm(alpha=1 / period, adjust=False).mean()
        atr_series = pd.Series(np.nan, index=tr.index)
        atr_series.iloc[period:] = atr_smoothed.values
        return [_safe_float_for_json(x) for x in atr_series.tolist()]

    def _dm(self) -> Tuple[pd.Series, pd.Series]:
        high = self.df["High"]
        low = self.df["Low"]
        up = high.diff()
        down = -low.diff()
        plus_dm = up.where((up > down) & (up > 0), 0.0)
        minus_dm = down.where((down > up) & (down > 0), 0.0)
        plus_dm.iloc[0] = 0
        minus_dm.iloc[0] = 0
        return plus_dm, minus_dm

    def dm(self) -> Tuple[List[float], List[float]]:
        plus_dm, minus_dm = self._dm()
        return (plus_dm.fillna(0).tolist(), minus_dm.fillna(0).tolist())

    def adx(self, period: int = 14) -> List[Optional[float]]:
        atr_list = self.atr(period)
        atr_vals = np.array([(x if x is not None else np.nan) for x in atr_list], dtype=float)
        plus_dm, minus_dm = self._dm()
        alpha = 1 / period
        sp_init = pd.Series(
            [plus_dm.iloc[1 : period + 1].mean()],
            index=[plus_dm.index[period]],
        )
        sm_init = pd.Series(
            [minus_dm.iloc[1 : period + 1].mean()],
            index=[minus_dm.index[period]],
        )
        smooth_plus = pd.concat([sp_init, plus_dm.iloc[period + 1 :]]).ewm(
            alpha=alpha, adjust=False
        ).mean()
        smooth_minus = pd.concat([sm_init, minus_dm.iloc[period + 1 :]]).ewm(
            alpha=alpha, adjust=False
        ).mean()
        sp = np.zeros(len(atr_vals))
        sm = np.zeros(len(atr_vals))
        sp[period:] = smooth_plus.values
        sm[period:] = smooth_minus.values
        pdi = np.where(atr_vals > 0, 100 * sp / atr_vals, 0)
        mdi = np.where(atr_vals > 0, 100 * sm / atr_vals, 0)
        di_sum = pdi + mdi
        dx = np.where(di_sum > 0, 100 * np.abs(pdi - mdi) / di_sum, 0)
        dx[:period] = np.nan
        adx_init = pd.Series([np.nanmean(dx[period : 2 * period])])
        adx_smoothed = pd.concat([adx_init, pd.Series(dx[2 * period :])]).ewm(
            alpha=alpha, adjust=False
        ).mean()
        adx_series = np.full(len(atr_vals), np.nan)
        adx_series[2 * period - 1] = adx_smoothed.iloc[0]
        adx_series[2 * period :] = adx_smoothed.values[1:]
        return [_safe_float_for_json(x) for x in adx_series.tolist()]

    # Data access
    def to_iloc(self, index: Optional[Union[int, str]] = None) -> int:
        """convert given index to integer location index"""
        if index is None:
            return self.df.index.size - 1
        if isinstance(index, (int, np.integer)):
            return min(max(0, int(index)), self.df.index.size - 1)
        date = pd.Timestamp(index)
        i = self.df.index.get_indexer([date], method="ffill")[0]
        return max(0, min(i, self.df.index.size - 1))

    def get_candle(
        self,
        index: Optional[Union[int, str]] = None,
    ) -> Tuple[float, float, float, float]:
        i = self.to_iloc(index)
        return (
            float(self.df["Open"].iloc[i]),
            float(self.df["High"].iloc[i]),
            float(self.df["Low"].iloc[i]),
            float(self.df["Close"].iloc[i]),
        )

    def price(self, index: Optional[Union[int, str]] = None) -> float:
        i = self.to_iloc(index)
        return float(self.df["Close"].iloc[i])
