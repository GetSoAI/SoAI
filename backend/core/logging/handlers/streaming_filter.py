"""SoAI - Streaming log feedback suppression filter [backend/core/logging/handlers/streaming_filter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import override

__all__ = ("StreamingFeedbackFilter",)


class StreamingFeedbackFilter(logging.Filter):
    def __init__(self, source_file: str) -> None:
        super().__init__()
        self._source_file = source_file

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            pathname = record.pathname
        except AttributeError:
            pathname = ""
        return pathname != self._source_file
