# AceMarket

A full-stack paper trading and Python strategy IDE backtester.

MIT — see [LICENSE](LICENSE) for details.

## Dev startup

- In one terminal: `cd backend && uvicorn api:app`
- In another terminal: `cd frontend && npm run dev`

If you get an error, you may need to update the yfinance package:
```bash
cd backend && pip install -U yfinance
```

## Documentation

- **[Strategy Rules](docs/STRATEGY_RULES.md)** — Exact rules for writing strategy code (what you can/cannot use, data access, lifecycle)
- **[API Reference](docs/API.md)** — Full API endpoint documentation with request/response formats