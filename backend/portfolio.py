"""Portfolio tracking, metrics and position management"""

class Portfolio:
    def __init__(self):
        self._positions = {}  # symbol -> {"stock": Stock, "quantity": float (signed), "avg_price": float, "realized_pnl": float}
        self._realized = {}  # symbol -> realized pnl across all closed lots/trades
        self.cash = 0
        self.slippage = 0  # decimal, e.g. 0.001 = 0.1%
        self.share_min_pct = 10  # min increment as % of share: 100=whole, 10=0.1, 1=0.01
        self.commission = 0  # decimal pct (0.01 = 1%)
        self.commission_per_order = 0.0  # $ per order
        self.commission_per_share = 0.0  # $ per share
        # Risk / constraints (defaults are permissive)
        self.allow_short = True
        self.max_positions = 0  # 0 => unlimited
        self.max_position_pct = 0.0  # 0 => unlimited
        self.min_cash_reserve_pct = 0.0  # keep this pct of equity in cash (long buys)
        self.min_trade_value = 0.0
        self.max_trade_value = 0.0  # 0 => unlimited
        self.max_order_qty = 0  # 0 => unlimited
        # Margin model (very simplified)
        # short_margin_requirement = 1.5 approximates Reg-T initial margin:
        # short sale proceeds are credited to cash, but 150% of short MV is reserved.
        self.short_margin_requirement = 1.5
        self.trade_log = []
        self.equity_curve = []  # [(index, value), ...] after each trade

    def _trade_meta(self, stock, index):
        """Best-effort metadata for a fill: (iloc_index, YYYY-MM-DD time string)."""
        try:
            i = int(index)
        except Exception:
            i = None
        try:
            if i is None:
                i = stock.df.index.size - 1
            i = max(0, min(i, stock.df.index.size - 1))
            t = stock.df.index[i]
            ts = t.isoformat()[:10]
        except Exception:
            ts = None
        return i, ts

    def _append_equity(self, value):
        self.equity_curve.append({"i": len(self.trade_log), "v": value})

    @property
    def stocks(self):
        return [(p["stock"], p["quantity"]) for p in self._positions.values()]

    def get_position(self, stock_or_symbol):
        symbol = stock_or_symbol.symbol if hasattr(stock_or_symbol, "symbol") else str(stock_or_symbol)
        symbol = symbol.upper()
        return self._positions.get(symbol)

    def positions(self):
        return list(self._positions.values())

    def _round_qty(self, qty: float) -> float:
        """Round quantity to nearest share_min_pct increment (e.g. 10% = 0.1 share)."""
        inc = float(self.share_min_pct or 100) / 100.0
        if inc >= 1:
            return float(round(qty))
        return round(round(float(qty) / inc) * inc, 2)

    def _slippage_factor(self, side: str) -> float:
        """Slippage as decimal (e.g. 0.001 = 0.1%)."""
        slip = float(self.slippage or 0)
        if slip < 0 or slip >= 1:
            raise ValueError("Slippage must be in [0, 1)")
        return slip if side == "buy" else -slip

    def _fill_price(self, side, price):
        """
        Fill price with slippage only. Commission is applied separately via _compute_commission.
        Slippage is always an adverse move. 
        """
        price = float(price)
        slip = self._slippage_factor(side)
        if side == "buy":
            return price * (1 + slip)
        if side == "sell":
            return price * (1 - slip)
        raise ValueError("Invalid side")

    def _compute_commission(self, quantity: float, notional: float) -> float:
        """
        Commission: per-order + per-share, or pct of notional if those are zero.
        """
        per_order = float(self.commission_per_order or 0)
        per_share = float(self.commission_per_share or 0)
        pct = float(self.commission or 0)
        if per_order > 0 or per_share > 0:
            return per_order + per_share * abs(float(quantity))
        if pct > 0:
            return notional * pct
        return 0.0

    def estimate_fill_price(self, side, raw_price):
        """Public helper for strategy sizing: side in {'buy','sell'}."""
        return self._fill_price(side, raw_price)

    def estimate_buy_cost(self, quantity, raw_price):
        """Total cost to buy (fill price + commission). Use for cash checks before enter_position_long."""
        qty = self._round_qty(float(quantity))
        if qty <= 0:
            return 0.0
        fill = self._fill_price("buy", raw_price)
        notional = fill * qty
        commission = self._compute_commission(qty, notional)
        return notional + commission

    def estimate_sell_proceeds(self, quantity, raw_price):
        """Net proceeds from sell (fill price - commission). Use for sizing before exit_position."""
        qty = self._round_qty(float(quantity))
        if qty <= 0:
            return 0.0
        fill = self._fill_price("sell", raw_price)
        notional = fill * qty
        commission = self._compute_commission(qty, notional)
        return notional - commission

    def max_affordable_buy(self, raw_price, reserve_fraction=0.05):
        """Max quantity affordable to buy with (1 - reserve_fraction) of cash. Returns 0 if none."""
        fill = self._fill_price("buy", raw_price)
        if fill <= 0:
            return 0.0
        max_cost = float(self.cash) * (1.0 - reserve_fraction)
        inc = max(0.001, float(self.share_min_pct or 100) / 100.0)
        qty = self._round_qty(max_cost / fill)
        if qty <= 0:
            return 0.0
        cost = self.estimate_buy_cost(qty, raw_price)
        while cost > max_cost and qty > 0:
            qty = self._round_qty(max(0, qty - inc))
            if qty <= 0:
                return 0.0
            cost = self.estimate_buy_cost(qty, raw_price)
        return qty if cost <= max_cost else 0.0

    def _positions_view(self):
        # symbol -> (stock, qty)
        out = {}
        for sym, p in self._positions.items():
            try:
                out[sym] = (p["stock"], float(p["quantity"]))
            except Exception:
                continue
        return out

    def get_short_market_value(self, index=None):
        short_mv = 0.0
        for stock, quantity in self.stocks:
            q = float(quantity)
            if q < 0:
                short_mv += float(stock.price(index)) * abs(q)
        return float(short_mv)

    def get_reserved_cash(self, index=None):
        equity = float(self.get_value(index))
        short_mv = float(self.get_short_market_value(index))
        short_reserve = float(self.short_margin_requirement) * short_mv if short_mv > 0 else 0.0
        cash_reserve = float(self.min_cash_reserve_pct) * max(0.0, equity) if self.min_cash_reserve_pct else 0.0
        return float(short_reserve + cash_reserve)

    def get_buying_power(self, index=None):
        # "Spendable" cash after reserving collateral + cash reserve.
        bp = float(self.cash) - float(self.get_reserved_cash(index))
        return float(bp)

    def _reserved_cash_projected(self, *, cash_after, positions_after, index):
        equity = float(cash_after)
        short_mv = 0.0
        for _, (stock, qty) in positions_after.items():
            px = float(stock.price(index))
            equity += px * float(qty)
            if float(qty) < 0:
                short_mv += px * abs(float(qty))
        short_reserve = float(self.short_margin_requirement) * float(short_mv) if short_mv > 0 else 0.0
        cash_reserve = float(self.min_cash_reserve_pct) * max(0.0, equity) if self.min_cash_reserve_pct else 0.0
        return float(short_reserve + cash_reserve)

    def _check_order_common(self, stock, side, quantity, trade_index, raw_price, fill_price, trade_value, cost_cash_change):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.max_order_qty and float(quantity) > float(self.max_order_qty):
            raise ValueError(f"Order qty exceeds max_order_qty ({self.max_order_qty})")

        if self.min_trade_value and float(trade_value) < float(self.min_trade_value):
            raise ValueError("Trade value is below minimum")
        if self.max_trade_value and float(trade_value) > float(self.max_trade_value):
            raise ValueError("Trade value exceeds maximum")

        symbol = stock.symbol.upper()
        pos = self._positions.get(symbol)
        if pos is None and self.max_positions and len(self._positions) >= int(self.max_positions):
            raise ValueError(f"Max positions reached ({self.max_positions})")

        equity_pre = float(self.get_value(trade_index))
        if self.max_position_pct and equity_pre > 0:
            cap = float(equity_pre) * float(self.max_position_pct)
            if float(trade_value) > cap + 1e-9:
                raise ValueError("Trade exceeds max_position_pct cap")

        if side == "buy":
            # Keep some cash on hand after buys
            if self.min_cash_reserve_pct and equity_pre > 0:
                reserve = float(equity_pre) * float(self.min_cash_reserve_pct)
                cash_after = float(self.cash) - float(trade_value)
                if cash_after < reserve - 1e-9:
                    raise ValueError("Trade would violate cash reserve")

        # Cash check for buys/cover
        if float(cost_cash_change) < 0:
            need = abs(float(cost_cash_change))
            if float(self.cash) + 1e-9 < need:
                raise ValueError("Not enough cash to enter position")

        # Margin / buying power check
        positions_after = self._positions_view()
        cur_qty = float(positions_after.get(symbol, (stock, 0))[1])
        delta_qty = float(quantity) if side == "buy" else -float(quantity)
        post_qty = cur_qty + delta_qty
        if post_qty == 0:
            positions_after.pop(symbol, None)
        else:
            positions_after[symbol] = (stock, post_qty)

        cash_after = float(self.cash) + float(cost_cash_change)
        reserved_after = self._reserved_cash_projected(cash_after=cash_after, positions_after=positions_after, index=trade_index)
        buying_power_after = float(cash_after) - float(reserved_after)
        if buying_power_after < -1e-6:
            raise ValueError("Insufficient buying power (margin)")

    def enter_position_long(self, stock, quantity, index=None):
        quantity = self._round_qty(float(quantity))
        if (index is None):
            index = stock.df.index.size - 1
        trade_index, trade_time = self._trade_meta(stock, index)
        raw_price = stock.price(trade_index)
        price = self._fill_price("buy", raw_price)
        notional = price * quantity
        commission = self._compute_commission(quantity, notional)
        cost = notional + commission
        self._check_order_common(
            stock=stock,
            side="buy",
            quantity=quantity,
            trade_index=trade_index,
            raw_price=raw_price,
            fill_price=price,
            trade_value=cost,
            cost_cash_change=-cost,
        )
        symbol = stock.symbol.upper()
        pos = self._positions.get(symbol)

        realized = 0.0
        if pos is None:
            self._positions[symbol] = {"stock": stock, "quantity": quantity, "avg_price": float(price), "realized_pnl": float(self._realized.get(symbol, 0.0))}
        else:
            qty0 = float(pos["quantity"])
            avg0 = float(pos["avg_price"])
            if qty0 >= 0:
                new_qty = qty0 + quantity
                new_avg = ((avg0 * qty0) + (price * quantity)) / new_qty if new_qty else 0.0
                pos["stock"] = stock
                pos["quantity"] = new_qty
                pos["avg_price"] = float(new_avg)
            else:
                cover_qty = min(quantity, abs(qty0))
                realized = (avg0 - price) * cover_qty
                remaining = quantity - cover_qty
                new_qty = qty0 + cover_qty
                if new_qty == 0 and remaining == 0:
                    self._positions.pop(symbol, None)
                else:
                    if new_qty == 0 and remaining > 0:
                        pos["stock"] = stock
                        pos["quantity"] = remaining
                        pos["avg_price"] = float(price)
                    else:
                        pos["stock"] = stock
                        pos["quantity"] = new_qty
                pos = self._positions.get(symbol)
                if pos is not None:
                    pos["realized_pnl"] = float(self._realized.get(symbol, 0.0) + realized)
        if realized != 0.0:
            self._realized[symbol] = float(self._realized.get(symbol, 0.0) + realized)
            if symbol in self._positions:
                self._positions[symbol]["realized_pnl"] = float(self._realized.get(symbol, 0.0))

        self.trade_log.append({
            'type': 'long',
            'stock': stock.symbol,
            'quantity': quantity,
            'price': float(raw_price),
            'fill_price': float(price),
            'cost': float(cost),
            'commission': float(commission),
            'realized_pnl': float(realized),
            'index': int(trade_index) if trade_index is not None else None,
            'time': trade_time,
        })
        self.cash -= cost
        self._append_equity(self.get_value(trade_index))

    def enter_position_short(self, stock, quantity, index=None):
        quantity = self._round_qty(float(quantity))
        if (index is None):
            index = stock.df.index.size - 1
        trade_index, trade_time = self._trade_meta(stock, index)
        if not self.allow_short:
            raise ValueError("Short selling is disabled")
        raw_price = stock.price(trade_index)
        price = self._fill_price("sell", raw_price)
        notional = price * quantity
        commission = self._compute_commission(quantity, notional)
        proceeds = notional - commission
        self._check_order_common(
            stock=stock,
            side="sell",
            quantity=quantity,
            trade_index=trade_index,
            raw_price=raw_price,
            fill_price=price,
            trade_value=notional,
            cost_cash_change=proceeds,
        )
        symbol = stock.symbol.upper()
        pos = self._positions.get(symbol)

        realized = 0.0
        if pos is None:
            self._positions[symbol] = {"stock": stock, "quantity": -quantity, "avg_price": float(price), "realized_pnl": float(self._realized.get(symbol, 0.0))}
        else:
            qty0 = float(pos["quantity"])
            avg0 = float(pos["avg_price"])
            if qty0 <= 0:
                new_qty = qty0 - quantity
                old_abs = abs(qty0)
                new_abs = abs(new_qty)
                new_avg = ((avg0 * old_abs) + (price * quantity)) / new_abs if new_abs else 0.0
                pos["stock"] = stock
                pos["quantity"] = new_qty
                pos["avg_price"] = float(new_avg)
            else:
                sell_qty = min(quantity, qty0)
                realized = (price - avg0) * sell_qty
                remaining = quantity - sell_qty
                new_qty = qty0 - sell_qty
                if new_qty == 0 and remaining == 0:
                    self._positions.pop(symbol, None)
                else:
                    if new_qty == 0 and remaining > 0:
                        pos["stock"] = stock
                        pos["quantity"] = -remaining
                        pos["avg_price"] = float(price)
                    else:
                        pos["stock"] = stock
                        pos["quantity"] = new_qty
                pos = self._positions.get(symbol)
                if pos is not None:
                    pos["realized_pnl"] = float(self._realized.get(symbol, 0.0) + realized)
        if realized != 0.0:
            self._realized[symbol] = float(self._realized.get(symbol, 0.0) + realized)
            if symbol in self._positions:
                self._positions[symbol]["realized_pnl"] = float(self._realized.get(symbol, 0.0))

        self.trade_log.append({
            'type': 'short',
            'stock': stock.symbol,
            'quantity': quantity,
            'price': float(raw_price),
            'fill_price': float(price),
            'proceeds': float(proceeds),
            'commission': float(commission),
            'realized_pnl': float(realized),
            'index': int(trade_index) if trade_index is not None else None,
            'time': trade_time,
        })
        self.cash += proceeds
        self._append_equity(self.get_value(trade_index))

    def exit_position(self, stock, quantity, index=None):
        quantity = self._round_qty(float(quantity))
        if (index is None):
            index = stock.df.index.size - 1
        trade_index, trade_time = self._trade_meta(stock, index)
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        symbol = stock.symbol.upper()
        pos = self._positions.get(symbol)
        if pos is None:
            raise ValueError("Stock not found in portfolio")
        qty0 = float(pos["quantity"])
        if quantity > abs(qty0):
            raise ValueError("Quantity exceeds position size")
        avg0 = float(pos["avg_price"])
        raw_price = stock.price(trade_index)

        if qty0 > 0:
            fill = self._fill_price("sell", raw_price)
            notional = fill * quantity
            commission = self._compute_commission(quantity, notional)
            amount = notional - commission
            realized = (fill - avg0) * quantity - commission
            new_qty = qty0 - quantity
            self.cash += amount
        else:
            fill = self._fill_price("buy", raw_price)
            notional = fill * quantity
            commission = self._compute_commission(quantity, notional)
            amount = -(notional + commission)
            realized = (avg0 - fill) * quantity - commission
            new_qty = qty0 + quantity
            self.cash += amount

        pos["stock"] = stock
        pos["quantity"] = new_qty
        self._realized[symbol] = float(self._realized.get(symbol, 0.0) + realized)
        pos["realized_pnl"] = float(self._realized.get(symbol, 0.0))
        if new_qty == 0:
            self._positions.pop(symbol, None)

        self.trade_log.append({
            'type': 'exit',
            'stock': stock.symbol,
            'quantity': quantity,
            'price': float(raw_price),
            'fill_price': float(fill),
            'amount': float(amount),
            'commission': float(commission),
            'realized_pnl': float(realized),
            'index': int(trade_index) if trade_index is not None else None,
            'time': trade_time,
        })
        self._append_equity(self.get_value(trade_index))

    def get_value(self, index=None):
        value = self.cash
        for stock, quantity in self.stocks:
            idx = index if index is not None else stock.df.index.size - 1
            value += float(stock.price(idx)) * float(quantity)
        return value

    def add_cash(self, amount):
        self.cash += amount

    def restore_from_state(self, cash: float, positions_data: list, trade_log: list, equity_curve: list, realized: dict, get_stock):
        """Restore portfolio from persisted state. get_stock(symbol) returns Stock instance."""
        self.cash = float(cash)
        self.trade_log = list(trade_log or [])
        self.equity_curve = list(equity_curve or [])
        self._realized = dict(realized or {})
        self._positions = {}
        for p in positions_data or []:
            sym = (p.get("symbol") or "").upper()
            if not sym:
                continue
            qty = float(p.get("quantity", 0))
            if qty == 0:
                continue
            try:
                stock = get_stock(sym)
            except Exception:
                continue
            self._positions[sym] = {
                "stock": stock,
                "quantity": qty,
                "avg_price": float(p.get("avg_price", 0)),
                "realized_pnl": float(p.get("realized_pnl", 0)),
            }

    def set_slippage(self, slippage):
        self.slippage = slippage

    def set_share_min_pct(self, pct: float):
        self.share_min_pct = max(0.0, float(pct))

    def set_commission(self, commission):
        self.commission = commission

    def set_commission_per_order(self, amount):
        self.commission_per_order = amount

    def set_commission_per_share(self, amount):
        self.commission_per_share = amount

    def set_allow_short(self, allow_short: bool):
        self.allow_short = bool(allow_short)

    def set_short_margin_requirement(self, short_margin_requirement: float):
        self.short_margin_requirement = float(short_margin_requirement)

    def set_constraints(
        self,
        *,
        max_positions=None,
        max_position_pct=None,
        min_cash_reserve_pct=None,
        min_trade_value=None,
        max_trade_value=None,
        max_order_qty=None,
    ):
        if max_positions is not None:
            self.max_positions = int(max_positions)
        if max_position_pct is not None:
            self.max_position_pct = float(max_position_pct)
        if min_cash_reserve_pct is not None:
            self.min_cash_reserve_pct = float(min_cash_reserve_pct)
        if min_trade_value is not None:
            self.min_trade_value = float(min_trade_value)
        if max_trade_value is not None:
            self.max_trade_value = float(max_trade_value)
        if max_order_qty is not None:
            self.max_order_qty = int(max_order_qty)

    def clear_history(self, initial_cash):
        """Reset portfolio: clear positions, trade log, equity curve; set cash to initial."""
        self._positions = {}
        self._realized = {}
        self.cash = initial_cash
        self.trade_log = []
        self.equity_curve = []