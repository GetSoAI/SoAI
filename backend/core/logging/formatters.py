"""SoAI - Unified console and JSON logging formatter implementation [backend/core/logging/formatters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import logging
import os
import re
import sys
from typing import TYPE_CHECKING, override

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.colors import get_log_level_colors, get_log_segment_colors
from core.logging.formatter_support import (
    ANSI_CODE_PATTERN,
    ANSI_RESET,
    ROOT_LOGGER_NAME,
    normalize_component_name,
    strip_ansi_codes,
)
from core.logging.log_record import SoAILogRecord
from core.logging.soai_error_log_formatting import (
    build_soai_error_log_suffix,
    extract_soai_error_payload,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.state.state_log_formatting import format_state_tokens_for_log
from core.timing.formatting import timestamp_to_utc_format, timestamp_to_utc_iso_no_z

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("UnifiedFormatter",)

OPERATION = "core.logging.formatters.is_color_supported"


_UTILS_AVAILABLE = True


class UnifiedFormatter(logging.Formatter):
    _ANSI_CODE_PATTERN = ANSI_CODE_PATTERN

    def __init__(
        self,
        fmt: str | None,
        date_fmt: str | None = None,
        use_colors: bool = False,
        use_json: bool = False,
    ) -> None:
        super().__init__(fmt, date_fmt)
        self.use_colors, self.use_json = (
            use_colors and self._is_color_supported(),
            use_json,
        )
        self._lc: dict[str, str]
        self._sc: dict[str, str]
        if _UTILS_AVAILABLE:
            self._lc, self._sc = (dict(get_log_level_colors()), dict(get_log_segment_colors()))
            self._rc = self._lc.get("RESET", ANSI_RESET)
        else:
            self._lc = dict.fromkeys(
                ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "RESET"), ""
            )
            self._sc = dict.fromkeys(
                ("TIMESTAMP", "COMPONENT", "MESSAGE", "LEVEL_DEFAULT", "SEPARATOR"), ""
            )
            self._rc = ""

    @staticmethod
    def _is_color_supported() -> bool:
        if _UTILS_AVAILABLE and sys.platform == "win32":
            try:
                kernel32 = ctypes.windll.kernel32
                handle, mode = (kernel32.GetStdHandle(-11), ctypes.c_ulong())
                if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    return False
                if mode.value & 4 == 0:
                    mode.value |= 4
                    if not kernel32.SetConsoleMode(handle, mode):
                        return False
                return True
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logging.getLogger(ROOT_LOGGER_NAME),
                    exception,
                    message="Failed while probing Windows console mode for color support (non-critical).",
                    operation=OPERATION,
                    level="debug",
                )
                return False
        if "JOURNAL_STREAM" in os.environ:
            return True
        try:
            isatty_method = sys.stdout.isatty
        except AttributeError:
            isatty_method = None
        return bool(callable(isatty_method) and isatty_method())

    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        if datefmt is not None:
            return timestamp_to_utc_format(record.created, datefmt)
        return timestamp_to_utc_iso_no_z(record.created)

    @override
    def format(self, record: logging.LogRecord) -> str:
        original_name = record.name
        try:
            if not original_name.startswith("["):
                normalized_component = normalize_component_name(original_name)
                record.name = f"[{normalized_component}]"
            soai_error_payload = extract_soai_error_payload(record)
            suffix = build_soai_error_log_suffix(soai_error_payload)
            if self.use_json:
                output_dict: JSONDict = {
                    "message": strip_ansi_codes(record.getMessage()),
                    "timestamp": timestamp_to_utc_iso_no_z(record.created),
                    "level": record.levelname,
                    "logger": record.name,
                    "pathname": record.pathname,
                    "lineno": record.lineno,
                }
                trace_id_value: str | None = None
                record_trace_id = record.trace_id if isinstance(record, SoAILogRecord) else None
                if isinstance(record_trace_id, str) and record_trace_id:
                    trace_id_value = record_trace_id
                elif soai_error_payload is not None:
                    payload_trace_id = soai_error_payload.get("trace_id")
                    if isinstance(payload_trace_id, str) and payload_trace_id:
                        trace_id_value = payload_trace_id
                if trace_id_value:
                    output_dict["trace_id"] = trace_id_value
                if record.exc_info:
                    output_dict["exc_info"] = self.formatException(record.exc_info)
                if soai_error_payload is not None:
                    output_dict["soai_error"] = dict(soai_error_payload)
                return serialize_json_compact_stable_strict(output_dict)
            formatted_message = super().format(record)
            if self.use_colors:
                first_line, *remaining_lines = formatted_message.splitlines()
                parts = first_line.split(" - ", 3)
                timestamp, component, level_name, message = (parts + [""] * 4)[:4]
                message = f"{message}{suffix}" if suffix else message
                message = format_state_tokens_for_log(message)
                remaining_lines = [format_state_tokens_for_log(line) for line in remaining_lines]
                level_color = self._lc.get(record.levelname, self._sc["LEVEL_DEFAULT"])
                separator = f"{self._sc['SEPARATOR']} - {self._rc}"
                colored_first_line = separator.join(
                    [
                        f"{self._sc['TIMESTAMP']}{timestamp}{self._rc}",
                        f"{self._sc['COMPONENT']}{component}{self._rc}",
                        f"{level_color}{level_name}{self._rc}",
                        f"{self._sc['MESSAGE']}{message}{self._rc}",
                    ],
                )
                return (
                    f"{colored_first_line}\n{self._sc['MESSAGE']}{chr(10).join(remaining_lines)}{self._rc}"
                    if remaining_lines
                    else colored_first_line
                )
            if suffix:
                first_line, *remaining_lines = formatted_message.splitlines()
                formatted_message = "\n".join([f"{first_line}{suffix}", *remaining_lines])
            return re.sub(self._ANSI_CODE_PATTERN, "", formatted_message)
        finally:
            record.name = original_name
