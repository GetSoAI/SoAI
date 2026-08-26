"""SoAI - Bootstrap logging helpers [backend/core/logging/bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import sys
from typing import override

from core.errors.trace_logging import ensure_trace_logging
from core.logging.palette import get_palette_colors
from core.runtime.environment_flags import is_soai_gui_launched
from core.timing.formatting import timestamp_to_utc_log_format, utc_now_log_format

__all__ = (
    "emit_gui_status",
    "setup_bootstrap_logger",
    "transition_bootstrap_loggers_to_runtime_logging",
)

BOOTSTRAP_LOGGER_NAMES: tuple[str, ...] = ("SoAI.Bootstrap", "SoAI.Lifecycle")


def setup_bootstrap_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    ensure_trace_logging()
    logger = logging.getLogger(name)
    if not logger.handlers:
        if is_soai_gui_launched():
            logger.setLevel(logging.CRITICAL)
            logger.addHandler(logging.NullHandler())
        else:
            handler = logging.StreamHandler(sys.stderr)
            palette = get_palette_colors()
            color_map = {
                "DEBUG": palette["grey"],
                "INFO": palette["green"],
                "WARNING": palette["orange"],
                "ERROR": palette["red"],
                "CRITICAL": palette["ruby"],
            }
            tag_color = palette["component"]
            timestamp_color = palette["timestamp"]
            separator_color = palette["grey"]
            reset = palette["white"].replace("[97m", "[0m")

            class _ColorFormatter(logging.Formatter):
                @override
                def format(self, record: logging.LogRecord) -> str:
                    color = color_map.get(record.levelname, "")
                    created = timestamp_to_utc_log_format(record.created)
                    message = record.getMessage()
                    tag_name = record.name.replace(".", "/")
                    result = (
                        f"{timestamp_color}{created}{reset} "
                        f"{separator_color}-{reset} "
                        f"{tag_color}[{tag_name}]{reset} "
                        f"{separator_color}-{reset} "
                        f"{color}{record.levelname}{reset} "
                        f"{separator_color}-{reset} "
                        f"{message}"
                    )
                    if record.exc_info:
                        exc_text = self.formatException(record.exc_info)
                        if exc_text:
                            result = f"{result}\n{exc_text}"
                    return result

            formatter = _ColorFormatter("%(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(level)
    logger.propagate = False
    return logger


def transition_bootstrap_loggers_to_runtime_logging() -> None:
    for logger_name in BOOTSTRAP_LOGGER_NAMES:
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True


def emit_gui_status(message: str) -> None:
    if is_soai_gui_launched():
        sys.stdout.write(f"{utc_now_log_format()} - [SoAI/Bootstrap] - INFO - {message}\n")
        sys.stdout.flush()
