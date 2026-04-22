"""Centralised logging configuration."""
from __future__ import annotations

import logging
import logging.config
from typing import Any, Dict

from .config import settings


def configure_logging() -> None:
    """Configure root logger based on settings. Idempotent."""
    level = settings.log_level.upper()

    formatters: Dict[str, Any]
    if settings.env == "prod":
        formatters = {
            "default": {
                "format": '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
            },
        }
    else:
        formatters = {
            "default": {
                "format": "%(asctime)s %(levelname)-7s %(name)s — %(message)s",
                "datefmt": "%H:%M:%S",
            },
        }

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": level,
            },
        },
        "loggers": {
            "uvicorn": {"level": level, "handlers": ["console"], "propagate": False},
            "uvicorn.error": {"level": level, "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "httpx": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "openai": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "chromadb": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        },
        "root": {"level": level, "handlers": ["console"]},
    }
    logging.config.dictConfig(config)
