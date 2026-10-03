"""SoAI - Plugin log file entry shaping [backend/core/logging/plugin_log_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.logging.formatter_support import strip_ansi_codes
from core.timing.formatting import utc_now_iso
from core.types.json import JSONDict

__all__ = ("build_plugin_log_entry", "parse_plugin_log_line")

_LOG_LEVEL_PATTERN_TEXT: str = (
    r"^\[(?P<process_level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\](?:\s+|$)"
    r"|^(?P<plain_level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)(?:\s+|:\s*|$)"
    r"|^(?:\d{4}-\d{2}-\d{2} [^\n]+? - \[[^\n]+?\] - )"
    r"(?P<record_level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL) - "
)


def parse_plugin_log_line(line: str) -> tuple[str, str]:
    text = strip_ansi_codes(line).strip()
    level_match = re.search(_LOG_LEVEL_PATTERN_TEXT, text, flags=re.IGNORECASE)
    level = "INFO"
    message = text
    if level_match is not None:
        level = str(
            level_match.group("process_level")
            or level_match.group("plain_level")
            or level_match.group("record_level")
        ).upper()
        if level_match.group("process_level") is not None:
            message = text[level_match.end() :]
    if level == "WARN":
        level = "WARNING"
    return level, message


def build_plugin_log_entry(source: str, line: str) -> JSONDict:
    text = strip_ansi_codes(line).strip()
    level, message = parse_plugin_log_line(text)
    return {
        "timestamp": utc_now_iso(),
        "component": f"Plugin/{source}",
        "level": level,
        "message": message,
        "text": text,
    }
