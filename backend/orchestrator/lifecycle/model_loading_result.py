"""SoAI - Model loading outcome contracts [backend/orchestrator/lifecycle/model_loading_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.error_types import ErrorType
from core.errors.exceptions import StateError
from core.errors.payload import ErrorPublicPayload

__all__ = ("ModelLoadingResult", "ModelScopedLoadError")


class ModelScopedLoadError(StateError):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class ModelLoadingResult:
    loaded: bool
    terminal_failure: bool
    message: str | None = None
    error_type: ErrorType = ErrorType.SERVER_ERROR
    allow_failover: bool = True
    public_error: ErrorPublicPayload | None = None

    @classmethod
    def success(cls) -> ModelLoadingResult:
        return cls(loaded=True, terminal_failure=False)

    @classmethod
    def deferred(cls) -> ModelLoadingResult:
        return cls(loaded=False, terminal_failure=False)

    @classmethod
    def failed(
        cls,
        message: str,
        *,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
        allow_failover: bool = True,
        public_error: ErrorPublicPayload | None = None,
    ) -> ModelLoadingResult:
        return cls(
            loaded=False,
            terminal_failure=True,
            message=message,
            error_type=error_type,
            allow_failover=allow_failover,
            public_error=public_error,
        )
