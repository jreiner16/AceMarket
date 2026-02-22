# AceMarket Deployment Guide

## Local Development (with auth)

1. **Firebase setup**
   - Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
   - Enable Email/Password authentication
   - Create a web app and copy the config to `frontend/.env`
   - In Project Settings > Service Accounts, generate a new private key
   - Save the JSON file and set `GOOGLE_APPLICATION_CREDENTIALS` to its path

2. **Backend**
   ```bash
   cd backend
   # Create .env with GOOGLE_APPLICATION_CREDENTIALS
   pip install -r requirements.txt
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Frontend**
   ```bash
   cd frontend
   # Create .env with Firebase config (VITE_FIREBASE_*)
   npm install && npm run dev
   ```

## Local Development (auth bypass)

For quick local testing without Firebase, set **both** `ENVIRONMENT=development` and `DISABLE_AUTH=1` (auth bypass is blocked in production):

```bash
cd backend
ENVIRONMENT=development DISABLE_AUTH=1 uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The frontend will still require Firebase login. For a fully auth-free flow, you'd need to modify the frontend to skip the splash page when the backend is in dev mode.

## Docker

```bash
# Build
docker build -t acemarket .

# Run (with volume for SQLite persistence)
docker run -p 8000:8000 \
  -v acemarket-data:/data \
  -e GOOGLE_APPLICATION_CREDENTIALS=/data/firebase-key.json \
  -e ACEMARKET_DB=/data/acemarket.db \
  acemarket
```

**Note:** The Docker image builds the frontend but does not serve it. You need a reverse proxy (nginx, Caddy) to serve the static files from `/app/frontend/dist` and proxy `/api` to the backend. Or deploy frontend separately (e.g. Firebase Hosting, Vercel).

### Example nginx config

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /app/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Production Checklist

- [ ] Set `GOOGLE_APPLICATION_CREDENTIALS` or use GCP workload identity
- [ ] Set `CORS_ORIGINS` to your frontend domain(s)
- [ ] Set `ENVIRONMENT=production` (required for production; default is development)
- [ ] **SQLite:** Use `uvicorn api:app --workers 1` (SQLite does not support multi-process)
- [ ] **PostgreSQL:** Use `--workers 4` when migrated to a proper DB
- [ ] Use HTTPS (terminate at load balancer or reverse proxy)
- [ ] Configure Firebase Security Rules for Storage
- [ ] Run `acemarket.db` on a persistent volume

## Database Migrations

Schema changes use Alembic. After modifying `db.py` or adding tables:

```bash
cd backend
alembic revision -m "description"
# Edit alembic/versions/xxx_description.py with upgrade/downgrade
alembic upgrade head
```
