"""SoAI - Math expression errors [backend/core/math/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("MathExpressionError",)


class MathExpressionError(Exception):
    message: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = str(message)
