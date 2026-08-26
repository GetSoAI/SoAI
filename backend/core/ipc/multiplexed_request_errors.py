"""SoAI - Multiplexed IPC request error conversion [backend/core/ipc/multiplexed_request_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from core.errors.exceptions import ServiceUnavailableError

__all__ = (
    "raise_ipc_request_failure",
    "raise_ipc_request_timeout",
)


def raise_ipc_request_timeout(
    exception: TimeoutError,
    *,
    worker_id: int,
    method: str,
) -> NoReturn:
    raise ServiceUnavailableError(
        "IPC request timed out.",
        operation="core.ipc.multiplexed.request.timeout",
        details={"worker_id": int(worker_id), "method": method},
        cause=exception,
    ) from exception


def raise_ipc_request_failure(
    exception: BaseException,
    *,
    worker_id: int,
    method: str,
) -> NoReturn:
    if isinstance(exception, ServiceUnavailableError):
        raise exception
    raise ServiceUnavailableError(
        "IPC request failed.",
        operation="core.ipc.multiplexed.request.failed",
        details={"worker_id": int(worker_id), "method": method},
        cause=exception,
    ) from exception
