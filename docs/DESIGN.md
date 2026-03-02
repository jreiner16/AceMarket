# Design Decisions & Limitations

## Fill Timing

**Fills are modeled at the open of the next bar after the signal.**

When your strategy calls `enter_position_long`, `enter_position_short`, or `exit_position` during `update(open, high, low, close, index)`, the fill price is the **open of the next bar** (bar `index + 1`). This is a conservative assumption: you observe OHLC at bar end, place the order, and it gets filled at the next bar's open. On the last bar of the backtest, where no next bar exists, the fill falls back to the current bar's close.

## Monte Carlo OHLC Model

Monte Carlo builds synthetic price paths by bootstrap-sampling historical returns. The high/low for each synthetic bar are **approximated** from the open/close using a simple volatility-based range. This model is suitable for:

- Long-horizon path analysis
- Probabilistic outcome distributions
- Non-intraday strategies

It is **not** suitable for intraday or high-frequency simulation. For production-grade stochastic modeling, consider Parkinson, Garman-Klass, or full stochastic volatility models.

## Overfitting & Walk-Forward

The platform supports train/test splits (e.g. 70/30) for walk-forward validation. **Be aware of overfitting:**

- Tuning parameters on the train set and testing once on the test set can still overfit if you iterate.
- Run the same strategy on **multiple symbols** to check robustness.
- Use **out-of-sample** periods (e.g. train 2018–2020, test 2021–2022, then again 2023–2024).
- Check **parameter sensitivity**: small changes in parameters should not collapse performance.

The platform does not enforce these practices; they are your responsibility.
