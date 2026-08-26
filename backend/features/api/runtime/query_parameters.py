"""SoAI - API query parameter validation [backend/features/api/runtime/query_parameters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Container

from fastapi import Request

from features.api.runtime.errors import raise_invalid_request

__all__ = ("require_supported_query_parameters",)


def require_supported_query_parameters(
    request: Request,
    *,
    allowed_keys: Container[str],
) -> None:
    for key in request.query_params:
        if key not in allowed_keys:
            raise_invalid_request(request, "Unsupported query parameters.")
