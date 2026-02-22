"""Application configuration and constants."""
import os
import logging

# Load .env from backend directory when running uvicorn
_env_dir = os.path.dirname(os.path.abspath(__file__))
_env_file = os.path.join(_env_dir, ".env")
if os.path.isfile(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

# CORS: restrict to frontend origin(s). Comma-separated for multiple.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]

# Stock cache
STOCK_CACHE_MAX = 64
STOCK_CACHE_TTL_SEC = 60 * 60

# Rate limiting (in-memory; use Redis for multi-worker)
RATE_LIMIT_STRATEGY_WINDOW_SEC = 60
RATE_LIMIT_STRATEGY_MAX = 5
RATE_LIMIT_GENERAL_WINDOW_SEC = 60
RATE_LIMIT_GENERAL_MAX = 100

# Environment: development, staging, production. Default development for easy local run.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# Auth bypass: in development, bypass when Firebase creds missing or DISABLE_AUTH=1
_creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if _creds_path and not os.path.isabs(_creds_path):
    _creds_path = os.path.join(_env_dir, _creds_path.lstrip("./"))
if _creds_path and os.path.isfile(_creds_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _creds_path
_has_firebase_creds = _creds_path and os.path.isfile(_creds_path)
_explicit_disable = os.environ.get("DISABLE_AUTH", "").lower() in ("1", "true", "yes")
_explicit_enable = os.environ.get("DISABLE_AUTH", "").lower() in ("0", "false", "no")
if IS_PRODUCTION:
    DISABLE_AUTH = False
elif _explicit_enable:
    DISABLE_AUTH = False
elif _explicit_disable or not _has_firebase_creds:
    DISABLE_AUTH = True  # Bypass when no creds (can't verify) or explicit
else:
    DISABLE_AUTH = False

# Database
DB_PATH = os.environ.get("ACEMARKET_DB", "acemarket.db")

# Numeric tolerance for float comparisons
FLOAT_TOLERANCE = 1e-9
MARGIN_TOLERANCE = 1e-6

# Symbol validation (e.g. BRK.B, BHF-A)
SYMBOL_MAX_LEN = 12
SYMBOL_ALLOWED_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")

# Run history limit
MAX_RUNS_PER_USER = 25

# Strategy code limits
STRATEGY_CODE_MAX_LEN = 50_000

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
