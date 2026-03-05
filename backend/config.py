"""App config"""
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
# In production, no fallback — empty CORS_ORIGINS means no origins allowed (fail-safe).
_cors_raw = os.environ.get("CORS_ORIGINS", "").strip()
if not _cors_raw:
    CORS_ORIGINS = []  # set after IS_PRODUCTION below
else:
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]

# Stock cache
STOCK_CACHE_MAX = 64
STOCK_CACHE_TTL_SEC = 60 * 60

# Rate limiting (in-memory per process; use Redis for multi-worker production)
RATE_LIMIT_STRATEGY_WINDOW_SEC = 60
RATE_LIMIT_STRATEGY_MAX = 5
RATE_LIMIT_GENERAL_WINDOW_SEC = 60
RATE_LIMIT_GENERAL_MAX = 100

# Environment: development, staging, production. Default development for easy local run.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# CORS: in production require explicit origins; in dev allow localhost when unset
if not _cors_raw:
    CORS_ORIGINS = [] if IS_PRODUCTION else ["http://localhost:5173", "http://127.0.0.1:5173"]
if IS_PRODUCTION and not CORS_ORIGINS:
    logging.warning("CORS_ORIGINS is empty in production; set it to your frontend origin(s).")

# Auth bypass: in development, bypass when Firebase creds missing or DISABLE_AUTH=1
_creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "") or os.environ.get("FIREBASE_CREDENTIALS_BASE64", "")
_creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if _creds_path and not os.path.isabs(_creds_path):
    _creds_path = os.path.join(_env_dir, _creds_path.lstrip("./"))
if _creds_path and os.path.isfile(_creds_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _creds_path
_has_firebase_creds = bool(_creds_json) or (_creds_path and os.path.isfile(_creds_path))
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

# Database: use PostgreSQL when DATABASE_URL is set (production, e.g. Render);
# otherwise use SQLite (local dev). SQLite on Render is ephemeral — data is lost on restart.
_raw_db_url = os.environ.get("DATABASE_URL", "").strip()
# Render uses postgres://; psycopg2 expects postgresql://
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1) if _raw_db_url.startswith("postgres://") else _raw_db_url
DB_PATH = os.environ.get("ACEMARKET_DB", "acemarket.db")

# Force auth on when production DB is used (prevent accidental bypass)
if DATABASE_URL and DISABLE_AUTH:
    logging.warning("DATABASE_URL is set; disabling auth bypass for safety.")
    DISABLE_AUTH = False

# P0: Refuse to run in production with DISABLE_AUTH explicitly set
if IS_PRODUCTION and _explicit_disable:
    import sys
    logging.critical("DISABLE_AUTH must not be set when ENVIRONMENT=production.")
    sys.exit(1)

# Bounds for user inputs (prevent overflow/DoS)
MAX_INITIAL_CASH = 1e12  # cap initial_cash to avoid float inf / JSON issues
MAX_ORDER_QUANTITY = 10_000_000  # global cap on position size per order

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
STRATEGY_NAME_MAX_LEN = 200

# Input caps (DoS prevention)
SEARCH_QUERY_MAX_LEN = 200
MAX_WATCHLIST_QUOTES_SYMBOLS = 50
MAX_BACKTEST_SYMBOLS = 30
DATE_STR_MAX_LEN = 16  # YYYY-MM-DD or similar

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
