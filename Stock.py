import yfinance as yf
import pandas as pd
import mplfinance as mpf
import numpy as np

_PLOT_STYLE = None

def _get_plot_style():
    """
    Simple getter for the plot style.
    """
    global _PLOT_STYLE
    if _PLOT_STYLE is None:
        mc = mpf.make_marketcolors(up='green', down='red', edge='inherit', wick='inherit')
        _PLOT_STYLE = mpf.make_mpf_style(marketcolors=mc, gridstyle='-', gridcolor='#37474f', facecolor='#1e1e1e', figcolor='#1e1e1e', edgecolor='#78909c', rc={'axes.labelcolor': '#b0bec5', 'xtick.color': '#b0bec5', 'ytick.color': '#b0bec5'})
    return _PLOT_STYLE

class Stock:
    def __init__(self, symbol):
        self.symbol = symbol
        self._tr_cache = None
        self.df = yf.download(symbol, period="max", interval="1d", auto_adjust=True, progress=False)
        if self.df.empty:
            print("[ACE]: No data for " + self.symbol + "!")
            return
        # use only first field (ticker) for columns
        if isinstance(self.df.columns, pd.MultiIndex):
            self.df.columns = self.df.columns.get_level_values(0)
        # convert to datetime
        self.df.index = pd.to_datetime(self.df.index)
        # sort by index
        self.df = self.df.sort_index()
        for col in ['Open', 'High', 'Low', 'Close']:
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        self.df = self.df.dropna()
        print("[ACE]: Loaded data for " + self.symbol + "!")

    def plot(self, start_date, end_date):
        sliced = self.df[pd.to_datetime(start_date):pd.to_datetime(end_date)]
        mpf.plot(sliced, type='candle', style=_get_plot_style())

    # indicators
    def rsi(self, period=14):
        close = self.df['Close']
        # calculate delta series
        delta = close.diff()
        # calculate gain/lossseries
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        # calculate average gain/loss series
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        # calculate relative strength index series
        rs = avg_gain / avg_loss
        rsi_series = 100 - (100 / (1 + rs))
        # RSI = 100 when avg_loss is 0
        rsi_series = rsi_series.where(avg_loss > 0, 100.0)
        # fill initial period with 0
        rsi_series = rsi_series.fillna(0.0)
        # match original: zeros for first period
        rsi_series.iloc[:period] = 0.0
        return rsi_series.tolist()

    def sma(self, period=14):
        # calculate sma series using optimized rolling pandas function
        return self.df['Close'].rolling(window=period).mean().fillna(0).tolist()

    def ema(self, period=14):
        # calculate ema series using optimized ewm (exponential weighted moving average) pandas function
        return self.df['Close'].ewm(span=period, adjust=False).mean().fillna(0).tolist()

    def macd(self, long_period=26, short_period=12):
        # calculate short/long ema series
        short_ema = self.df['Close'].ewm(span=short_period, adjust=False).mean()
        long_ema = self.df['Close'].ewm(span=long_period, adjust=False).mean()
        # calculate macd series with fillna(0) to avoid NaN values
        macd_series = (short_ema - long_ema).fillna(0)
        # set initial period to 0
        macd_series.iloc[:long_period] = 0
        return macd_series.tolist()

    def bollinger_bands(self, period=20, dev=2):
        close = self.df['Close']
        # calculate sma and std series
        sma = close.rolling(window=period).mean().fillna(0)
        std = close.rolling(window=period).std().fillna(0)
        # calculate upper, middle, lower bands
        upper = sma + dev * std
        middle = sma
        lower = sma - dev * std
        return list(zip(upper.tolist(), middle.tolist(), lower.tolist()))

    def _tr_series(self):
        if self._tr_cache is not None:
            return self._tr_cache
        high = self.df['High']
        low = self.df['Low']
        prev_close = self.df['Close'].shift(1)
        hl = high - low
        hc = (high - prev_close).abs()
        lc = (low - prev_close).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        tr.iloc[0] = hl.iloc[0]
        self._tr_cache = tr
        return tr

    def tr(self, index=None):
        i = self.to_iloc(index)
        if i == 0:
            return float(self.df['High'].iloc[0] - self.df['Low'].iloc[0])
        tr_vals = self._tr_series()
        return float(tr_vals.iloc[i])

    def atr(self, period=14):
        tr = self._tr_series()
        tr_from_period = pd.concat([
            pd.Series([tr.iloc[1:period + 1].mean()], index=[tr.index[period]]),
            tr.iloc[period + 1:]
        ])
        atr_smoothed = tr_from_period.ewm(alpha=1 / period, adjust=False).mean()
        atr_series = pd.Series(0.0, index=tr.index)
        atr_series.iloc[period:] = atr_smoothed.values
        return atr_series.tolist()

    def _dm(self):
        high = self.df['High']
        low = self.df['Low']
        up = high.diff()
        down = -low.diff()
        plus_dm = up.where((up > down) & (up > 0), 0.0)
        minus_dm = down.where((down > up) & (down > 0), 0.0)
        plus_dm.iloc[0] = 0
        minus_dm.iloc[0] = 0
        return plus_dm, minus_dm

    def dm(self):
        plus_dm, minus_dm = self._dm()
        return (plus_dm.fillna(0).tolist(), minus_dm.fillna(0).tolist())

    def adx(self, period=14):
        atr_vals = np.array(self.atr(period))
        plus_dm, minus_dm = self._dm()
        alpha = 1 / period
        sp_init = pd.Series([plus_dm.iloc[1:period + 1].mean()], index=[plus_dm.index[period]])
        sm_init = pd.Series([minus_dm.iloc[1:period + 1].mean()], index=[minus_dm.index[period]])
        smooth_plus = pd.concat([sp_init, plus_dm.iloc[period + 1:]]).ewm(alpha=alpha, adjust=False).mean()
        smooth_minus = pd.concat([sm_init, minus_dm.iloc[period + 1:]]).ewm(alpha=alpha, adjust=False).mean()
        sp = np.zeros(len(atr_vals))
        sm = np.zeros(len(atr_vals))
        sp[period:] = smooth_plus.values
        sm[period:] = smooth_minus.values
        pdi = np.where(atr_vals > 0, 100 * sp / atr_vals, 0)
        mdi = np.where(atr_vals > 0, 100 * sm / atr_vals, 0)
        di_sum = pdi + mdi
        dx = np.where(di_sum > 0, 100 * np.abs(pdi - mdi) / di_sum, 0)
        dx[:period] = 0
        adx_init = pd.Series([np.mean(dx[period:2 * period])])
        adx_smoothed = pd.concat([adx_init, pd.Series(dx[2 * period:])]).ewm(alpha=alpha, adjust=False).mean()
        adx_series = np.zeros(len(atr_vals))
        adx_series[2 * period - 1] = adx_smoothed.iloc[0]
        adx_series[2 * period:] = adx_smoothed.values[1:]
        return adx_series.tolist()

    def to_iloc(self, index=None):
        if index is None:
            return self.df.index.size - 1
        if isinstance(index, (int, np.integer)):
            return min(max(0, index), self.df.index.size - 1)
        date = pd.Timestamp(index)
        i = self.df.index.get_indexer([date], method='ffill')[0]
        return max(0, min(i, self.df.index.size - 1))

    def get_candle(self, index=None):
        i = self.to_iloc(index)
        return self.df['Open'].iloc[i], self.df['High'].iloc[i], self.df['Low'].iloc[i], self.df['Close'].iloc[i]

    def price(self, index=None):
        i = self.to_iloc(index)
        return self.df['Close'].iloc[i]
