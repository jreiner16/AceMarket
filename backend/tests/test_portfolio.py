"""Unit tests for portfolio module."""
import pytest
from portfolio import Portfolio
from stock import Stock


@pytest.fixture
def portfolio():
    p = Portfolio()
    p.add_cash(100_000)
    return p


@pytest.fixture
def stock():
    return Stock("AAPL")


def test_add_cash(portfolio):
    portfolio.add_cash(50_000)
    assert portfolio.cash == 150_000


def test_enter_position_long(portfolio, stock):
    portfolio.enter_position_long(stock, 10)
    assert portfolio.cash < 100_000
    pos = portfolio.get_position(stock)
    assert pos is not None
    assert pos["quantity"] == 10
    assert pos["avg_price"] > 0


def test_enter_position_short(portfolio, stock):
    portfolio.allow_short = True
    portfolio.enter_position_short(stock, 5)
    pos = portfolio.get_position(stock)
    assert pos is not None
    assert pos["quantity"] == -5


def test_exit_position(portfolio, stock):
    portfolio.enter_position_long(stock, 10)
    initial_cash = portfolio.cash
    portfolio.exit_position(stock, 5)
    pos = portfolio.get_position(stock)
    assert pos["quantity"] == 5
    assert portfolio.cash > initial_cash


def test_clear_history(portfolio, stock):
    portfolio.enter_position_long(stock, 10)
    portfolio.clear_history(50_000)
    assert portfolio.cash == 50_000
    assert len(portfolio.positions()) == 0
    assert len(portfolio.trade_log) == 0


def test_get_value(portfolio, stock):
    portfolio.enter_position_long(stock, 10)
    value = portfolio.get_value()
    assert value > portfolio.cash
    assert value == portfolio.cash + 10 * float(stock.price())


def test_quantity_must_be_positive(portfolio, stock):
    with pytest.raises(ValueError, match="Quantity must be positive"):
        portfolio.enter_position_long(stock, 0)
    with pytest.raises(ValueError, match="Quantity must be positive"):
        portfolio.enter_position_long(stock, -5)
