"""Strategy sandbox: whitelisted imports only."""
import pytest

from backtest import STRATEGY_ALLOWED_IMPORT_ROOTS, _validate_strategy_code, create_strategy_from_code
from portfolio import Portfolio
from stock import make_minimal_stock


def test_validate_rejects_disallowed_module():
    with pytest.raises(ValueError, match="Import 'os'"):
        _validate_strategy_code(
            "import os\n"
            "class S(Strategy):\n"
            "    def __init__(self, stock, portfolio):\n"
            "        super().__init__(stock, portfolio)\n"
        )


def test_validate_accepts_math_import():
    code = """
import math
class S(Strategy):
    def __init__(self, stock, portfolio):
        super().__init__(stock, portfolio)
    def update(self, o, h, l, c, index=None):
        _ = math.sqrt(4.0)
"""
    tree = _validate_strategy_code(code)
    assert tree is not None


def test_validate_rejects_relative_import():
    with pytest.raises(ValueError, match="Relative"):
        _validate_strategy_code(
            "from . import x\n"
            "class S(Strategy):\n"
            "    def __init__(self, stock, portfolio):\n"
            "        super().__init__(stock, portfolio)\n"
        )


def test_create_strategy_with_math_import():
    stock = make_minimal_stock("TEST")
    portfolio = Portfolio()
    code = """
import math
from statistics import mean

class MyStrategy(Strategy):
    def __init__(self, stock, portfolio):
        super().__init__(stock, portfolio)
        self.x = math.pi

    def update(self, o, h, l, c, index=None):
        if index == 0:
            _ = mean([1.0, 2.0, 3.0])
"""
    strat = create_strategy_from_code(stock, portfolio, code, block_lookahead=True)
    assert strat is not None
    assert abs(strat.x - 3.141592653589793) < 1e-9


def test_allowed_roots_is_sorted_documentation():
    """Keep frozenset explicit in source; this guards against accidental duplicates."""
    assert len(STRATEGY_ALLOWED_IMPORT_ROOTS) == len(set(STRATEGY_ALLOWED_IMPORT_ROOTS))
