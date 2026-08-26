"""SoAI - GPU slot mutation API error projection [backend/features/api/runtime/gpu_slot_error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from fastapi import status

from core.hardware.gpu_slot_failures import translate_gpu_slot_failure
from core.runtime.protocols import ConnectionProtocol
from core.types.json import JSONDict
from features.api.runtime.context import raise_api_error

__all__ = ("raise_slot_operation_error",)


def raise_slot_operation_error(request: ConnectionProtocol, result: JSONDict) -> NoReturn:
    status_code, code, message, details = translate_gpu_slot_failure(result)
    status_value = {
        400: status.HTTP_400_BAD_REQUEST,
        404: status.HTTP_404_NOT_FOUND,
        409: status.HTTP_409_CONFLICT,
        412: status.HTTP_412_PRECONDITION_FAILED,
        500: status.HTTP_500_INTERNAL_SERVER_ERROR,
        503: status.HTTP_503_SERVICE_UNAVAILABLE,
    }.get(status_code, status.HTTP_400_BAD_REQUEST)
    if status_value >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        raise_api_error(request, status_value, code, "Internal server error.")
    raise_api_error(request, status_value, code, message, extra=details)
