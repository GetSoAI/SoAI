"""SoAI - Recoverable exception classification policy [backend/core/errors/recoverable_exceptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import (
    DatabaseError,
    IpcRemoteRequestError,
    RateLimitError,
    ServiceUnavailableError,
    SoAITimeoutError,
)
from core.errors.external_service_exception import ExternalServiceError

__all__ = ("RECOVERABLE_EXCEPTIONS",)

RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    DatabaseError,
    ExternalServiceError,
    IpcRemoteRequestError,
    RateLimitError,
    ServiceUnavailableError,
    SoAITimeoutError,
    TimeoutError,
)
