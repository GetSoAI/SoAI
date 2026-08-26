"""SoAI - State-related application error types [backend/core/state/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import DatabaseError, PreconditionError, ValidationError

__all__ = (
    "CannotDeleteLastAdminError",
    "CannotDemoteLastAdminError",
    "DatabaseQueueSaturatedError",
    "DatabaseTimeoutError",
    "DatabaseUnavailableError",
    "DuplicateMCPServerError",
    "DuplicateProviderError",
)


class DatabaseUnavailableError(DatabaseError): ...


class DatabaseQueueSaturatedError(DatabaseError): ...


class DatabaseTimeoutError(DatabaseError):
    code: str | int = "database_timeout"
    http_status = 504
    is_transient = True

    @property
    def operation_id(self) -> str | None:
        if self.details:
            value = self.details.get("operation_id")
            return value if isinstance(value, str) else None
        return None

    @property
    def status_url(self) -> str | None:
        if self.details:
            value = self.details.get("status_url")
            return value if isinstance(value, str) else None
        return None

    @property
    def retry_guidance(self) -> str | None:
        if self.details:
            value = self.details.get("retry_guidance")
            return value if isinstance(value, str) else None
        return None

    @property
    def operation_status(self) -> str | None:
        if self.details:
            value = self.details.get("status")
            return value if isinstance(value, str) else None
        return None


class CannotDeleteLastAdminError(PreconditionError): ...


class CannotDemoteLastAdminError(PreconditionError): ...


class DuplicateProviderError(ValidationError): ...


class DuplicateMCPServerError(ValidationError): ...
