"""SoAI - Safe missing-model reference failure [backend/core/errors/model_reference_error.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("ModelReferenceNotFoundError",)


class ModelReferenceNotFoundError(ValidationError):
    code: str | int = "model_not_found"
    http_status = 400
    public_param: str | None = "model"
    public_message: str | None = (
        "The requested model was not found. Install or register it, or use an available API model ID."
    )
