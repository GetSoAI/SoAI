"""SoAI - Default config schema: log manager [backend/core/config/default_schema/log_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_log_manager_defaults",)


def build_log_manager_defaults() -> ConfigDict:
    return {
        "LOGGING": {
            "ENABLED": True,
            "LOGS_PATH": "logs",
            "LOG_LEVEL": "INFO",
            "MAIN_LOG": "soai.log",
            "CONSOLE_COLOR": True,
            "CONSOLE_LOGGING": True,
            "STREAMING_LOG_BUFFER_SIZE": 10_000,
            "MAIN_LOG_BACKUP_COUNT": 5,
            "LOGGING_SYSTEM": {
                "MAIN_LOG_ENABLE_JSON_LOGGING": False,
                "MAIN_LOG_COMPRESS_LOGS": False,
            },
            "AUDIT": {
                "PATH": "soai.audit.jsonl",
            },
        },
    }
