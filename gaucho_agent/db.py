"""Database engine, session management, and table initialization."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from gaucho_agent.config import settings

# Import all models so SQLModel registers their metadata
from gaucho_agent.models.source import Source  # noqa: F401
from gaucho_agent.models.event import Event  # noqa: F401
from gaucho_agent.models.dining import DiningMenuItem, DiningCommonsStatus  # noqa: F401
from gaucho_agent.models.sync_run import SyncRun  # noqa: F401

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = f"sqlite:///{settings.gaucho_db_path}"
        _engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
    return _engine


def init_db() -> None:
    """Create all tables and apply lightweight column migrations."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    # Add columns introduced after initial schema creation
    _migrate(engine)


def _migrate(engine) -> None:
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE dining_commons_status ADD COLUMN is_open_today INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE dining_commons_status ADD COLUMN status_date TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session and close it on exit."""
    engine = get_engine()
    with Session(engine) as session:
        yield session
