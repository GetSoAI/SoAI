"""SoAI - Network listener exceptions [backend/core/errors/network_exceptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ConflictError

__all__ = ("ApiPortConflictError", "ApiPortRangeExhaustedError")


class ApiPortConflictError(ConflictError):
    code: str | int = "api_port_conflict"


class ApiPortRangeExhaustedError(ConflictError):
    code: str | int = "api_port_range_exhausted"
