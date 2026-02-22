class Strategy:
    def __init__(self, stock, portfolio):
        self.stock = stock
        self.portfolio = portfolio

    def start(self, candle=None):
        """Called once at the beginning of the backtest."""
        pass

    def update(self, open, high, low, close, index=None):
        """Called for each candle during the backtest."""
        pass

    def end(self, candle=None):
        """Called once at the end of the backtest."""
        pass