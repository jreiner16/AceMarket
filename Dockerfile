# AceMarket — multi-stage build
# Build frontend
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --omit=dev
COPY frontend/ ./
RUN npm run build

# Backend + serve
FROM python:3.12-slim
WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --shell /bin/bash app

# Install backend deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy built frontend
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Ensure /data is writable by app user (for SQLite)
RUN mkdir -p /data && chown -R app:app /data /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend
ENV ACEMARKET_DB=/data/acemarket.db

USER app

EXPOSE 8000
WORKDIR /app/backend

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
