# Security

## Environment and secrets

- **Use the example files.** Copy `backend/.env.example` and `frontend/.env.example` to `.env` in each directory (or set env vars in your host). Do not commit `.env` files. Both `frontend/.env` and `backend/.env` are in `.gitignore`. Never force-add them or commit env files that contain secrets.
- **Frontend:** `VITE_*` variables are baked into the client bundle at build time. Use them only for non-secret configuration (e.g. `VITE_API_BASE`, Firebase client config). Firebase API keys in the client are expected; protect your app with Firebase Security Rules and Auth.
- **Backend:** Set secrets via the host environment or your platform’s secret store (e.g. Render env vars), not in repo:
  - `DATABASE_URL`
  - `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_BASE64`
  - `CORS_ORIGINS` (required in production)

## Production checklist

- Set `ENVIRONMENT=production` so auth cannot be bypassed and API docs are disabled.
- Set `CORS_ORIGINS` to your frontend origin(s). Empty CORS in production will trigger a warning.
- Ensure Firebase Admin credentials are configured so `DISABLE_AUTH` is never used in production. If `DATABASE_URL` is set, auth bypass is forced off.
- For multi-worker or multi-instance deployments, use Redis (or similar) for rate limiting and job state; in-memory stores are per-process.
