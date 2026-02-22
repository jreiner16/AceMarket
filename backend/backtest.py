import ast
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from stock import Stock
from portfolio import Portfolio
from strategy import Strategy

from config import STRATEGY_CODE_MAX_LEN

_FORBIDDEN_NAMES = {
    "__builtins__",
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "help",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "memoryview",
    "breakpoint",
    "__loader__",
    "__spec__",
    "__subclasses__",
    "__mro__",
    "__class__",
    "__bases__",
    "isinstance",
    "issubclass",
    "hasattr",
    "repr",
    "format",
    "bytes",
    "bytearray",
    "slice",
    "property",
    "staticmethod",
    "classmethod",
    "type",
    "object",
    "__doc__",
    "__globals__",
    "__code__",
    "__closure__",
}

# Strategy execution timeout (seconds)
STRATEGY_EXEC_TIMEOUT = 30

_ALLOWED_DUNDER_ATTRS = {
    "__init__",
}


def _validate_strategy_code(code: str) -> ast.AST:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are not allowed in strategy code")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ValueError("global/nonlocal are not allowed in strategy code")
        if isinstance(node, ast.Attribute) and isinstance(node.attr, str) and node.attr.startswith("__"):
            if node.attr not in _ALLOWED_DUNDER_ATTRS:
                raise ValueError("Access to dunder attributes is not allowed")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"Use of '{node.id}' is not allowed in strategy code")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
            raise ValueError(f"Calls to '{node.func.id}' are not allowed in strategy code")

    return tree


def _safe_builtins() -> dict:
    return {
        "__build_class__": __build_class__,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "print": print,
        "range": range,
        "len": len,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "enumerate": enumerate,
        "zip": zip,
        "next": next,
        "any": any,
        "all": all,
        "sorted": sorted,
        "super": super,
    }


def _exec_strategy_code(stock, portfolio, code):
    """Execute validated strategy code. Runs in thread with timeout."""
    tree = _validate_strategy_code(code)
    namespace = {
        "Strategy": Strategy,
        "__builtins__": _safe_builtins(),
        "__name__": "__strategy__",
    }
    exec(compile(tree, "<strategy>", "exec"), namespace)
    for name, obj in namespace.items():
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            return obj(stock, portfolio)
    raise ValueError("Code must define a class that inherits from Strategy")


def create_strategy_from_code(stock, portfolio, code):
    """Execute user code and return a Strategy instance. Code must define a class that inherits from Strategy."""
    if not code or not code.strip():
        raise ValueError("Strategy code cannot be empty")
    if len(code) > STRATEGY_CODE_MAX_LEN:
        raise ValueError(f"Strategy code exceeds maximum length ({STRATEGY_CODE_MAX_LEN})")
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_exec_strategy_code, stock, portfolio, code)
        try:
            return future.result(timeout=STRATEGY_EXEC_TIMEOUT)
        except FuturesTimeoutError:
            raise ValueError(f"Strategy execution timed out after {STRATEGY_EXEC_TIMEOUT}s")


class Backtest:
    def __init__(self, strategy, portfolio):
        self.strategy = strategy
        self.portfolio = portfolio

    def run(self, start_date, end_date):
        start_iloc = self.strategy.stock.to_iloc(start_date)
        end_iloc = self.strategy.stock.to_iloc(end_date)
        if start_iloc > end_iloc:
            return
        self.strategy.start(self.strategy.stock.get_candle(start_date))
        for candle in range(start_iloc, end_iloc + 1):
            open, high, low, close = self.strategy.stock.get_candle(candle)
            self.strategy.update(open, high, low, close, candle)
        self.strategy.end(self.strategy.stock.get_candle(end_date))