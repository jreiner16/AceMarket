"""Unit tests for backtest module."""
import pytest
from backtest import create_strategy_from_code, Backtest
from portfolio import Portfolio
from stock import Stock


def test_create_strategy_valid():
    stock = Stock("AAPL")
    port = Portfolio()
    port.add_cash(1000)
    code = """
class MyStrategy(Strategy):
    def start(self, candle=None):
        pass
    def update(self, o, h, l, c, i=None):
        pass
    def end(self, candle=None):
        pass
"""
    strat = create_strategy_from_code(stock, port, code)
    assert strat is not None
    assert hasattr(strat, "update")


def test_create_strategy_empty():
    stock = Stock("AAPL")
    port = Portfolio()
    port.add_cash(1000)
    with pytest.raises(ValueError, match="cannot be empty"):
        create_strategy_from_code(stock, port, "")


def test_create_strategy_no_class():
    stock = Stock("AAPL")
    port = Portfolio()
    port.add_cash(1000)
    with pytest.raises(ValueError, match="must define a class"):
        create_strategy_from_code(stock, port, "x = 1")


def test_create_strategy_import_forbidden():
    stock = Stock("AAPL")
    port = Portfolio()
    port.add_cash(1000)
    code = """
import os
class MyStrategy(Strategy):
    def start(self, c=None): pass
    def update(self, o,h,l,c,i=None): pass
    def end(self, c=None): pass
"""
    with pytest.raises(ValueError, match="Imports are not allowed"):
        create_strategy_from_code(stock, port, code)


def test_create_strategy_eval_forbidden():
    stock = Stock("AAPL")
    port = Portfolio()
    port.add_cash(1000)
    code = """
class MyStrategy(Strategy):
    def start(self, c=None): pass
    def update(self, o,h,l,c,i=None):
        eval("1+1")
    def end(self, c=None): pass
"""
    with pytest.raises(ValueError, match="not allowed"):
        create_strategy_from_code(stock, port, code)


def test_backtest_run():
    stock = Stock("AAPL")
    port = Portfolio()
    port.add_cash(100_000)
    code = """
class MyStrategy(Strategy):
    def start(self, c=None): pass
    def update(self, o, h, l, c, i=None): pass
    def end(self, c=None): pass
"""
    strat = create_strategy_from_code(stock, port, code)
    bt = Backtest(strat, port)
    bt.run("2023-01-01", "2023-06-01")
    assert port.get_value() >= 0
