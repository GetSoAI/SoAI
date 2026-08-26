"""SoAI - HTTP-aware recoverable exception tuple [backend/core/errors/http_recoverable.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

__all__ = ("HTTP_RECOVERABLE_EXCEPTIONS",)

HTTP_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    httpx2.RequestError,
)
