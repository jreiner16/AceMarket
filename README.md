# AceMarket
A full-stack paper trading and Python strategy IDE backtester and Monte Carlo simulator.

## Dev startup
- In one terminal: `cd backend && uvicorn api:app`
- In another terminal: `cd frontend && npm run dev`

## Documentation
- **[Strategy Rules](docs/STRATEGY_RULES.md)** — exact rules for writing a strategy in the IDE backtester.
- **[API Reference](docs/API.md)** — API endpoint documentation and explanation

## License
All Rights Reserved — see [LICENSE](LICENSE) for details. Use requires prior permission from the copyright holder. 

## Limitations
AceMarket is designed primarily as a simple, eductaional and conceptual tool for learning how to implement strategies, backtest them and simulate probable outcomes. It does not allow for accurate intraday trading, trading of actual shares. However, strategies implemented AceMarket this can easily be translated for implementation in real trading software.