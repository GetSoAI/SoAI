"""SoAI - Banner formatting utilities for logs [backend/core/logging/banner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from core.errors.exceptions import NotFoundError, ValidationError
from core.logging.colors import LOG_BANNER_MESSAGE_COLOR
from core.logging.formatter_support import ANSI_RESET
from core.logging.protocols import LoggerProtocol

__all__ = (
    "LogBannerSystem",
    "get_colorized_ascii_banner_lines",
)

ASCII_ART_BANNER = "\n::::::::::::::::::::::::::::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n::::::::#####::::::::::::#:::::#::::::::\n:::::::#:::::#::::::::::#:#::::#::::::::\n:::::::#:::::::::::::::#:::#:::#::::::::\n::::::::#####:::####::#######::#::::::::\n:::::::::::::#:#::::#:#:::::#::#::::::::\n:::::::#:::::#:#::::#:#:::::#::#::::::::\n::::::::#####:::####::#:::::#::#::::::::\n::::::::::::::::::::::::::::::::::::::::\n:::::::::::::::: soai.to :::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n::::::::::::::::::::::::::::::::::::::::\n"
_ANSI_GREY = "\x1b[90m"
_ANSI_WHITE = "\x1b[97m"
_ANSI_GREEN = "\x1b[92m"
_ANSI_RESET = "\x1b[0m"
_SO_AI_BOUNDARY_COLUMN = 21
_UTILS_AVAILABLE = True


def get_colorized_ascii_banner_lines() -> list[str]:
    colorized_lines: list[str] = []
    for line in ASCII_ART_BANNER.strip().splitlines():
        if "soai.to" in line:
            colorized_line = line.replace(":", f"{_ANSI_GREY}:{_ANSI_RESET}")
            colorized_line = colorized_line.replace(
                "soai.to",
                f"{_ANSI_WHITE}soai.to{_ANSI_RESET}",
            )
            colorized_lines.append(colorized_line)
            continue
        colorized_chars: list[str] = []
        for column_index, character in enumerate(line):
            if character == ":":
                colorized_chars.append(f"{_ANSI_GREY}:{_ANSI_RESET}")
            elif character == "#":
                if column_index < _SO_AI_BOUNDARY_COLUMN:
                    colorized_chars.append(f"{_ANSI_WHITE}#{_ANSI_RESET}")
                else:
                    colorized_chars.append(f"{_ANSI_GREEN}#{_ANSI_RESET}")
            else:
                colorized_chars.append(character)
        colorized_lines.append("".join(colorized_chars))
    return colorized_lines


class LogBannerSystem:

    def __init__(self, logger: LoggerProtocol, width: int) -> None:
        if width <= 0:
            raise ValidationError("Banner width must be positive.")
        if not isinstance(logger, logging.Logger):
            raise ValidationError("logger must be a logging.Logger instance.")
        self.logger = logger
        self.logger_name = logger.name
        self.width = width
        self._registry: dict[str, tuple[str, str, int]] = {}
        self._reset = ANSI_RESET if _UTILS_AVAILABLE else ""
        self._message_color = LOG_BANNER_MESSAGE_COLOR if _UTILS_AVAILABLE else ""

    def register(self, key: str, *, color: str, message: str, level: int = logging.INFO) -> None:
        if not key:
            raise ValidationError("Banner key cannot be empty.")
        if not color:
            raise ValidationError("Banner color must be a non-empty string.")
        if not message:
            raise ValidationError("Banner message must be a non-empty string.")
        self._registry[key] = (color, message, level)

    def emit(self, key: str, *, message: str | None = None, level: int | None = None) -> None:
        if key not in self._registry:
            raise NotFoundError(f"Banner '{key}' is not registered.")
        color, default_message, default_level = self._registry[key]
        self._render(
            color,
            message if message is not None else default_message,
            level if level is not None else default_level,
        )

    def emit_custom(self, *, color: str, message: str, level: int = logging.INFO) -> None:
        if not color:
            raise ValidationError("Banner color must be a non-empty string.")
        if not message:
            raise ValidationError("Banner message must be a non-empty string.")
        self._render(color, message, level)

    def has_banner(self, key: str) -> bool:
        return key in self._registry

    def _render(self, color: str, message: str, level: int) -> None:
        message_length = len(message) + 2
        if self.width < message_length:
            raise ValidationError("Banner width is smaller than the message payload.")
        left_count, remainder = divmod(self.width - message_length, 2)
        left_side, right_side, border = (
            ":" * left_count,
            ":" * left_count,
            ":" * self.width,
        )
        reset_code, message_color = (self._reset, self._message_color)
        self.logger.log(level, f"{color}{border}{reset_code}")
        message_padding = " " * remainder
        self.logger.log(
            level,
            f"{color}{left_side}{reset_code} {message_color}{message}{message_padding}{reset_code} {color}{right_side}{reset_code}",
        )
        self.logger.log(level, f"{color}{border}{reset_code}")
