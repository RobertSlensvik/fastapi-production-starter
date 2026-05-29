"""Structured logging with correlation IDs.

Uses structlog so logs are structured by default. In development they render
as colored key-value text; in production (APP_LOG_JSON=true) as JSON for
ingestion by log aggregators (Datadog, Loki, CloudWatch, etc.).

The request_id from `RequestIDMiddleware` is bound to a contextvar and
included automatically in every log line within that request's context.
"""

import logging
import sys
from contextvars import ContextVar

import structlog
from structlog.contextvars import merge_contextvars
from structlog.typing import EventDict, Processor

from app.config import Settings

# Contextvar holding the per-request correlation ID. Set by middleware.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_request_id(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Inject request_id from contextvar if present."""
    rid = request_id_var.get()
    if rid is not None:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging together.

    Stdlib loggers (uvicorn, sqlalchemy, etc.) are routed through structlog
    so all output uses the same format.
    """
    log_level = getattr(logging, settings.app_log_level)

    # Shared processors run on every event.
    shared_processors: list[Processor] = [
        merge_contextvars,
        _add_request_id,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_log_json:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logs (uvicorn, sqlalchemy) through structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quiet down noisy libraries
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given name."""
    return structlog.get_logger(name)
