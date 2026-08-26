"""SoAI - Uvicorn log filters [backend/core/logging/uvicorn_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import override

__all__ = ("UvicornConnectionDemoteFilter",)

_DEMOTED_MESSAGES = frozenset({"connection open", "connection closed"})


class UvicornConnectionDemoteFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage() in _DEMOTED_MESSAGES:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True
