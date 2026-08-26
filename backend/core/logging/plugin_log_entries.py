"""SoAI - Plugin log file entry shaping [backend/core/logging/plugin_log_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.logging.formatter_support import strip_ansi_codes
from core.timing.formatting import utc_now_iso
from core.types.json import JSONDict

__all__ = ("build_plugin_log_entry",)

_LOG_LEVEL_PATTERN_TEXT: str = r"\b(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b"


def build_plugin_log_entry(source: str, line: str) -> JSONDict:
    text = strip_ansi_codes(line).strip()
    level_match = re.search(_LOG_LEVEL_PATTERN_TEXT, text, flags=re.IGNORECASE)
    level = level_match.group(1).upper() if level_match else "INFO"
    if level == "WARN":
        level = "WARNING"
    return {
        "timestamp": utc_now_iso(),
        "component": f"Plugin/{source}",
        "level": level,
        "message": text,
        "text": text,
    }
