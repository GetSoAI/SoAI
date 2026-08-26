"""SoAI - Model reference resolution errors [backend/core/models/reference_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("UnknownModelReferenceError",)


class UnknownModelReferenceError(ValidationError): ...
