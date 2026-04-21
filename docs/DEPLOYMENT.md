# AceMarket Deployment Guide

## Architecture

- **Backend** — Python/FastAPI, deployed on [Render](https://render.com) via Docker
- **Database** — PostgreSQL on [Supabase](https://supabase.com) (free tier)
- **Frontend** — React/Vite, deployed on Firebase Hosting
- **Auth** — Firebase Authentication

## Backend (Render)

1. Push this repo to GitHub
2. Render Dashboard → New → Web Service → connect the repo
3. Set runtime to **Docker**, dockerfile path `./backend/Dockerfile`, context `./backend`
4. Set these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | **Yes** | Supabase session pooler URI (see below) |
| `CORS_ORIGINS` | **Yes** | Comma-separated frontend origins, e.g. `https://acemarketengine.web.app` |
| `ENVIRONMENT` | **Yes** | Set to `production` |
| `FIREBASE_CREDENTIALS_JSON` | **Yes** | Firebase Admin SDK service account JSON (paste the whole JSON as a string) |

5. Deploy. Tables are created automatically on first run.

## Database (Supabase)

1. Create a free project at [supabase.com](https://supabase.com)
2. From your project page click **Connect** → **Session pooler** tab
3. Copy the URI (format: `postgresql://postgres.xxxxx:password@aws-1-region.pooler.supabase.com:5432/postgres`)
4. Paste it as `DATABASE_URL` in your Render environment variables

Use the **Session pooler** (port 5432), not the direct connection or transaction pooler.

## Frontend (Firebase Hosting)

1. Copy `frontend/.env.example` → `frontend/.env` and fill in your Firebase config and `VITE_API_BASE`
2. `cd frontend && npm ci && npm run build`
3. `firebase deploy`

## Local Development

```bash
# Copy and fill in your credentials
cp backend/.env.example backend/.env

# Terminal 1 — backend (DISABLE_AUTH=1 skips Firebase for local dev)
cd backend && DISABLE_AUTH=1 uvicorn api:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

`DATABASE_URL` must be set in `backend/.env` even for local dev — the backend always uses PostgreSQL.

## Verifying Persistence

After deploying:

1. Create a strategy, run a backtest, place an order
2. Refresh the page — data should remain
3. Trigger a redeploy — data should still be there

If data disappears, check that `DATABASE_URL` is correctly set in Render.
