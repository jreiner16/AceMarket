# Strategy Rules

Strategy code must define a class that inherits from `Strategy`. Only use data at or before the current bar index in `update()`, anythinge else would be lookahead.

## Class Structure

- Define one class inheriting from `Strategy`
- `def __init__(self, stock, portfolio, my_param=10):` — first two args required. Custom params need defaults
- Call `super().__init__()`; base sets `self.stock`, `self.portfolio`

## Lifecycle Methods

- `start(self, candle=None)` — called once at backtest start
- `update(self, open, high, low, close, index=None)` — called every bar. **Only use data at or before `index`**
- `end(self, candle=None)` — called once at backtest end

## self.stock

- `stock.symbol` — ticker string
- `stock.price(index)` → float, close at bar `index`
- `stock.get_candle(index)` → (open, high, low, close) tuple
- `stock.to_iloc(index)` → int, convert date string or int to bar index

**Indicators** (return lists; index with `[index]`; check `index < len(series)` and `series[index] is not None`):

- `stock.sma(period=14)`, `stock.ema(period=14)`, `stock.rsi(period=14)`
- `stock.atr(period=14)`, `stock.adx(period=14)`
- `stock.macd(long_period=26, short_period=12)`
- `stock.bollinger_bands(period=20, dev=2)` → list of (upper, middle, lower) tuples
- `stock.tr(index)`, `stock.dm()`

## self.portfolio

- `portfolio.cash`, `portfolio.get_value(index)`, `portfolio.get_position(stock)`, `portfolio.stocks`
- `portfolio.estimate_fill_price('buy', price)`, `portfolio.estimate_buy_cost(qty, price)`
- `portfolio.max_affordable_buy(price, reserve_fraction=0.05)`
- `portfolio.enter_position_long(stock, qty, index)`, `portfolio.enter_position_short(stock, qty, index)`
- `portfolio.exit_position(stock, qty, index)`

## Forbidden (Lookahead Blocked)

No `stock.df`, `stock.df.iloc`, `.loc`, `.iat`, `.at`, `.values`, `.index`. Use `stock.price(index)`, `stock.get_candle(index)`, `stock.sma(14)[index]` instead.

## Forbidden Python

No `import`, `global`, `nonlocal`, `eval`, `exec`, `open`, `input`, `getattr`, `setattr`, `type`, `isinstance`, `hasattr`, `repr`, `format`, `bytes`, `bytearray`.

## Limits

- Code max 50,000 chars
- Init timeout 30s
- Strategy name must be unique and non-empty
