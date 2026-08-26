"""SoAI - Log color configuration and accessors [backend/core/logging/colors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from collections.abc import Mapping

from core.logging.palette import (
    ANSI_AMBER,
    ANSI_BLUE,
    ANSI_COMPONENT,
    ANSI_GREEN,
    ANSI_GREY,
    ANSI_ORANGE,
    ANSI_RED,
    ANSI_TIMESTAMP,
    ANSI_WHITE,
)

__all__ = (
    "get_log_level_colors",
    "get_log_segment_colors",
)

ANSI_RESET = "\x1b[0m"
ANSI_RED_BOLD = "\x1b[91m\x1b[1m"

LOG_BANNER_MESSAGE_COLOR = ANSI_WHITE

LOG_BANNER_DEFAULTS: tuple[tuple[str, str, str, int], ...] = (
    ("ready", ANSI_GREEN, "SoAI is ready, have fun!", logging.INFO),
    (
        "failure_shutdown",
        ANSI_RED_BOLD,
        "SoAI critical failure shutdown initiated",
        logging.CRITICAL,
    ),
    (
        "restart",
        ANSI_AMBER,
        "SoAI restart sequence initiated",
        logging.WARNING,
    ),
    (
        "manual_shutdown",
        ANSI_ORANGE,
        "SoAI application shutdown initiated",
        logging.WARNING,
    ),
    (
        "shutdown",
        ANSI_ORANGE,
        "SoAI shutdown sequence initiated",
        logging.WARNING,
    ),
    (
        "update",
        ANSI_BLUE,
        "SoAI application update sequence initiated",
        logging.INFO,
    ),
)


def get_log_level_colors() -> Mapping[str, str]:
    return {
        "TRACE": ANSI_GREY,
        "DEBUG": ANSI_BLUE,
        "INFO": ANSI_GREEN,
        "WARNING": ANSI_ORANGE,
        "ERROR": ANSI_RED,
        "CRITICAL": ANSI_RED_BOLD,
        "RESET": ANSI_RESET,
    }


def get_log_segment_colors() -> Mapping[str, str]:
    return {
        "TIMESTAMP": ANSI_TIMESTAMP,
        "COMPONENT": ANSI_COMPONENT,
        "MESSAGE": ANSI_WHITE,
        "LEVEL_DEFAULT": ANSI_WHITE,
        "SEPARATOR": ANSI_GREY,
    }
