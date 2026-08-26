"""SoAI - Streaming conversation message errors [backend/core/conversations/streaming_message_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("StreamingAssistantMessageAlreadyFinalizedError",)


class StreamingAssistantMessageAlreadyFinalizedError(ValidationError): ...
