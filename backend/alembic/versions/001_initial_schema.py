"""Initial schema (matches db.init_db).

Revision ID: 001
Revises:
Create Date: 2025-02-21

"""
from alembic import op

revision = "001"
down_revision = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id TEXT PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            user_id TEXT PRIMARY KEY,
            cash REAL NOT NULL,
            positions_json TEXT NOT NULL,
            trade_log_json TEXT NOT NULL,
            equity_curve_json TEXT NOT NULL,
            realized_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            strategy_id INTEGER NOT NULL,
            strategy_name TEXT NOT NULL,
            symbols_json TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            results_json TEXT NOT NULL,
            portfolio_json TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS runs")
    op.execute("DROP TABLE IF EXISTS strategies")
    op.execute("DROP TABLE IF EXISTS portfolios")
    op.execute("DROP TABLE IF EXISTS settings")
