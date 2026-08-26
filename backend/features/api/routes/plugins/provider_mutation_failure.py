"""SoAI - Provider mutation HTTP failure ownership [backend/features/api/routes/plugins/provider_mutation_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from fastapi import Request

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from features.api.runtime.errors import raise_invalid_request, raise_server_error

__all__ = ("raise_provider_mutation_failure",)

LOGGER_NAME = "SoAI.features.api.provider_mutation_failure"


def raise_provider_mutation_failure(
    request: Request,
    exception: ValidationError | ValueError | RuntimeError,
    *,
    operation: str,
    provider_id: str,
    action: str,
) -> NoReturn:
    if isinstance(exception, ValidationError | ValueError):
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message=f"Provider {action} request was invalid.",
            operation=operation,
            details={"provider_id": provider_id},
            level="debug",
        )
        raise_invalid_request(request, str(exception))
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=f"Provider {action} failed.",
        operation=operation,
        details={"provider_id": provider_id},
    )
    raise_server_error(request, f"An internal error occurred while {action} the provider.")
