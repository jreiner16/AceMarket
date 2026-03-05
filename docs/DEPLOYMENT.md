# AceMarket Deployment Guide

## Quick Start: Render Blueprint

If deploying to Render, you can use the included `render.yaml`:

1. Push this repo to GitHub
2. Render Dashboard → New → Blueprint
3. Connect the repo
4. Set `CORS_ORIGINS` and `FIREBASE_CREDENTIALS_JSON` when prompted (sync: false)
5. Deploy

The blueprint creates a PostgreSQL database and links `DATABASE_URL` automatically.

## Persistent Storage (CRITICAL)

**Your strategies, backtest/Monte Carlo runs, and positions are stored in a database.** Without persistent storage, all data is lost on every server restart.

### Render: Use PostgreSQL

Render's filesystem is **ephemeral**. SQLite files (`acemarket.db`) are wiped on every deploy and restart. You **must** use PostgreSQL for production.

1. **Create a PostgreSQL database** in the Render dashboard:
   - Dashboard → New → PostgreSQL
   - Choose a name (e.g. `acemarket-db`)
   - Select a region close to your web service
   - Free tier is sufficient for development

2. **Link the database to your web service**:
   - Open your web service → Environment
   - Add environment variable: `DATABASE_URL` → **From Database** → select your Postgres instance → `Internal Database URL`
   - Use the **Internal** URL (not External) for lower latency

3. **Deploy**. The backend automatically uses PostgreSQL when `DATABASE_URL` is set. Tables are created on first run.

### Environment Variables Summary

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | **Yes** (production) | PostgreSQL connection string. Render provides this when you link a Postgres DB. |
| `ACEMARKET_DB` | No (dev only) | SQLite path when `DATABASE_URL` is not set. Default: `acemarket.db` |
| `CORS_ORIGINS` | Yes | Comma-separated frontend origins (e.g. `https://acemarketengine.web.app`) |
| `ENVIRONMENT` | Yes | `production` for live |
| `FIREBASE_CREDENTIALS_JSON` or `GOOGLE_APPLICATION_CREDENTIALS` | Yes | Firebase Admin SDK for auth |

### Local Development

Without `DATABASE_URL`, the backend uses SQLite. Data persists in `acemarket.db` in the backend directory.

```bash
cd backend && uvicorn api:app
```

### Verifying Persistence

After deployment with Postgres:

1. Create a strategy, run a backtest, place an order
2. Refresh the page — data should remain
3. Trigger a redeploy — data should still be there

If data disappears on refresh or restart, `DATABASE_URL` is not set or the Postgres database is not linked correctly.
