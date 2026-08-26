"""SoAI - LogRecord shape and factory installation [backend/core/logging/log_record.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

__all__ = (
    "SoAILogRecord",
    "ensure_soai_log_record_factory",
)


class SoAILogRecord(logging.LogRecord):
    type SoAIErrorPayloadValue = (
        str
        | int
        | float
        | bool
        | None
        | dict[str, "SoAIErrorPayloadValue"]
        | list["SoAIErrorPayloadValue"]
    )

    trace_id: str | None = None
    plugin_name: str | None = None
    plugin: str | None = None
    plugin_id: str | None = None
    soai_error: dict[str, SoAIErrorPayloadValue] | None = None


def ensure_soai_log_record_factory() -> None:
    current_factory = logging.getLogRecordFactory()
    if current_factory is SoAILogRecord:
        return
    logging.setLogRecordFactory(SoAILogRecord)
