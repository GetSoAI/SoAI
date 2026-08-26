"""SoAI - Shared unexpected exception sets [backend/core/errors/unexpected_exceptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

__all__ = (
    "HANDLED_RUNTIME_EXCEPTIONS",
    "UNEXPECTED_RUNTIME_EXCEPTIONS",
)

UNEXPECTED_RUNTIME_EXCEPTIONS: tuple[type[Exception], ...] = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
HANDLED_RUNTIME_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    SoAIError,
    *UNEXPECTED_RUNTIME_EXCEPTIONS,
)
