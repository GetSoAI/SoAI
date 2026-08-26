"""SoAI - API runtime logging [backend/features/api/runtime/api_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = ("sanitize_command_for_logging",)

_SECRET_REPLACEMENTS: tuple[tuple[str, int, str], ...] = (
    (
        r"(?<!context_window_)(API_KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AUTH|KEY)[=:]\s*[\"']?([^\s\"']+)",
        re.IGNORECASE,
        r"\1=***REDACTED***",
    ),
    (
        r"(soai-|sk-|pk-|bearer\s+)[a-zA-Z0-9_-]{20,}",
        re.IGNORECASE,
        "***REDACTED_KEY***",
    ),
    (
        r"--password[=\s]+[^\s]+",
        re.IGNORECASE,
        "--password=***REDACTED***",
    ),
)


def sanitize_command_for_logging(command: str) -> str:
    result = command
    for pattern_text, flags, replacement in _SECRET_REPLACEMENTS:
        result = re.sub(pattern_text, replacement, result, flags=flags)
    return result
