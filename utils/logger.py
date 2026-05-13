"""
utils/logger.py
---------------
Structured logging for the entire agent system.
Uses structlog for JSON-compatible, agent-aware log records.
"""

import logging
import sys
import structlog
from core.config import settings


def _configure_stdlib_logging() -> None:
    """Configure Python's stdlib logging to feed into structlog."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "playwright", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _build_structlog_processors() -> list:
    """Return the processor chain for structlog."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(colors=True),
    ]


def setup_logging() -> None:
    """Call once at application startup to configure the logging stack."""
    _configure_stdlib_logging()
    structlog.configure(
        processors=_build_structlog_processors(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Return a structlog logger bound to *name*.

    Usage:
        logger = get_logger(__name__)
        logger.info("agent_started", agent="SearchAgent", query="AI tools")
    """
    return structlog.get_logger().bind(module=name)


# Run configuration immediately on import
setup_logging()
