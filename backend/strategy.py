class Strategy:
    """
    Base class for backtest strategies. Override start, update, and end.

    LOOK-AHEAD RULE: In update(open, high, low, close, index), you must only use data
    at or before `index`. Never access stock.df, .iloc, .loc, or index into indicator
    series beyond the current bar (e.g. sma(14)[index+1] is forbidden). Fills occur
    at bar close; you cannot use intra-bar High/Low for stops/limits.
    """

    def __init__(self, stock, portfolio):
        self.stock = stock
        self.portfolio = portfolio

    def start(self, candle=None):
        """Called once at the beginning of the backtest."""
        pass

    def update(self, open, high, low, close, index=None):
        """
        Called for each candle during the backtest. Only use data at or before index.
        """
        pass

    def end(self, candle=None):
        """Called once at the end of the backtest."""
        pass