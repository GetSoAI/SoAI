"""SoAI - Publication receipt timeout and failure exceptions [backend/core/events/publication_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ServiceUnavailableError, SoAITimeoutError

__all__ = (
    "HardDeadlineExceededError",
    "PublicationDeadlineExceededError",
    "PublicationFailedError",
)


class PublicationDeadlineExceededError(SoAITimeoutError):
    code: str | int = "publication_timeout"
    http_status = 504
    is_transient = True


class HardDeadlineExceededError(SoAITimeoutError):
    code: str | int = "deadline_timeout"
    http_status = 504
    is_transient = True


class PublicationFailedError(ServiceUnavailableError):
    code: str | int = "publication_failed"
    http_status = 503
    is_transient = True
