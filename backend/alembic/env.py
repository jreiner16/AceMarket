"""Alembic environment. Uses config.DB_PATH for SQLite."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from sqlalchemy import create_engine
from config import DB_PATH

config = context.config
config.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
