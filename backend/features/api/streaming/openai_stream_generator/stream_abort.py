"""SoAI - OpenAI stream generator abort signal [backend/features/api/streaming/openai_stream_generator/stream_abort.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import override

__all__ = ("OpenAIStreamAbortRequested",)


class OpenAIStreamAbortRequested(Exception):
    __slots__ = ("error_type", "message")

    def __init__(self, message: str, error_type: str) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type

    @override
    def __str__(self) -> str:
        return self.message

    def __getnewargs_ex__(self) -> tuple[tuple[str, str], dict[str, str]]:
        return ((self.message, self.error_type), {})
