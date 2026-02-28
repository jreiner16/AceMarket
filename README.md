# AceMarket

A full-stack paper trading and Python strategy IDE backtester.

## Dev startup

- In one terminal: `cd backend && uvicorn api:app`
- In another terminal: `cd frontend && npm run dev`

If you get an error, you may need to update the yfinance package:
```bash
cd backend && pip install -U yfinance
```

## Documentation

- **[Strategy Rules](docs/STRATEGY_RULES.md)** — exact rules for writing a strategy in the IDE backtester.
- **[API Reference](docs/API.md)** — API endpoint documentation and explanation

## License
BSD 3-Clause — see [LICENSE](LICENSE) for details. 
TLDR: use freely but attribution is required. 