"""SoAI - Model loading failure classification [backend/orchestrator/lifecycle/model_loading_failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.error_types import ErrorType
from core.errors.exceptions import IpcRemoteRequestError
from orchestrator.execution.failure_classification import resolve_remote_error_code
from orchestrator.lifecycle.model_loading_result import ModelScopedLoadError

__all__ = ("ModelLoadFailureClassification", "classify_model_load_failure")

MODEL_SCOPED_REMOTE_ERROR_CODES = frozenset(
    {
        ErrorType.INVALID_REQUEST.value,
        ErrorType.MODEL_OUTPUT_CONTRACT.value,
        ErrorType.ACCELERATOR_MEMORY_EXHAUSTED.value,
        ErrorType.SYSTEM_MEMORY_EXHAUSTED.value,
    },
)


@dataclass(frozen=True, slots=True)
class ModelLoadFailureClassification:
    model_scoped: bool
    reason: str


def classify_model_load_failure(exception: BaseException) -> ModelLoadFailureClassification:
    if isinstance(exception, ModelScopedLoadError):
        return ModelLoadFailureClassification(
            model_scoped=False,
            reason=exception.message,
        )
    if isinstance(exception, IpcRemoteRequestError):
        remote_error_code = resolve_remote_error_code(exception)
        return ModelLoadFailureClassification(
            model_scoped=remote_error_code in MODEL_SCOPED_REMOTE_ERROR_CODES,
            reason=exception.message,
        )
    return ModelLoadFailureClassification(
        model_scoped=False,
        reason=str(exception),
    )
