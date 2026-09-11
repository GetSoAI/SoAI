"""SoAI - Logging configuration constants [backend/core/logging/configuration_constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Final

__all__ = (
    "DEFAULT_JSON_LOG_FILENAME",
    "DEFAULT_LOGS_COMPRESSION_SUFFIX",
    "DEFAULT_LOG_DATE_FORMAT",
    "DEFAULT_LOG_ENCODING",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_LOG_HANDLER_TYPES",
    "DEFAULT_LOG_ROTATION_INTERVAL_COUNT",
    "DEFAULT_LOG_ROTATION_UTC",
    "DEFAULT_LOG_ROTATION_WHEN",
)

DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S UTC"
DEFAULT_LOG_ENCODING: Final[str] = "utf-8"
DEFAULT_JSON_LOG_FILENAME: Final[str] = "soai.log.json"
DEFAULT_LOGS_COMPRESSION_SUFFIX: Final[str] = ".gz"
DEFAULT_LOG_HANDLER_TYPES: Final[tuple[str, ...]] = ("file", "console", "stream")
DEFAULT_LOG_ROTATION_WHEN: Final[str] = "midnight"
DEFAULT_LOG_ROTATION_INTERVAL_COUNT: Final[int] = 1
DEFAULT_LOG_ROTATION_UTC: Final[bool] = True
