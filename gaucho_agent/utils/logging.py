"""Rich-based logger setup."""

from __future__ import annotations

import logging

from rich.logging import RichHandler

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a Rich handler. Idempotent."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring setup has run."""
    setup_logging()
    return logging.getLogger(name)
