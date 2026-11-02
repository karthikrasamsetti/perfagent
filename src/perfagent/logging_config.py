"""Structured logging for the agent (structlog).

One call to configure() sets up:
  - console output (readable key=value lines)
  - a rotating file at logs/perfagent.log (JSON lines, for later shipping to a log
    aggregator like Datadog / ELK)

Use get_logger(__name__) anywhere and log with key/value context, e.g.:
    log = get_logger(__name__)
    log.info("plan.drafted", plan_id=pid, scenarios=3)

GUARDRAIL DISCIPLINE: log what happened and counts — never raw secrets, tokens, or
request bodies. Log ids, targets, metric numbers, and category counts only.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

import structlog

_configured = False


def configure(level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure structlog once. Safe to call multiple times."""
    global _configured
    if _configured:
        return

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # stdlib logging: console (human) + rotating file (JSON)
    root = logging.getLogger()
    root.setLevel(level)

    # avoid duplicate handlers on reload
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler()
    console.setLevel(level)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        Path(log_dir) / "perfagent.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )

    # console = readable, file = JSON
    console.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=False),
        foreign_pre_chain=shared,
    ))
    file_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared,
    ))

    _configured = True


def get_logger(name: str = "perfagent"):
    if not _configured:
        configure()
    return structlog.get_logger(name)
