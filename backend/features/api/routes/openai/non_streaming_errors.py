"""SoAI - Canonical non-streaming OpenAI route errors [backend/features/api/routes/openai/non_streaming_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from core.runtime.protocols import RequestProtocol
from features.api.runtime.errors import (
    raise_bad_gateway,
    raise_gateway_timeout,
    raise_server_error,
)

__all__ = (
    "MALFORMED_STREAM_CHUNK_MESSAGE",
    "raise_malformed_stream_chunk_error",
    "raise_task_completed_without_result",
    "raise_task_succeeded_without_payload",
    "raise_task_timeout_error",
)

MALFORMED_STREAM_CHUNK_MESSAGE = (
    "Provider returned a malformed OpenAI SSE frame while buffering a non-streaming response."
)


def raise_malformed_stream_chunk_error(request: RequestProtocol) -> NoReturn:
    raise_bad_gateway(
        request,
        MALFORMED_STREAM_CHUNK_MESSAGE,
        error_type="invalid_stream_error",
    )


def raise_task_completed_without_result(request: RequestProtocol, message: str | None) -> NoReturn:
    raise_server_error(request, message or "Task completed without result.")


def raise_task_succeeded_without_payload(request: RequestProtocol) -> NoReturn:
    raise_bad_gateway(
        request,
        "Task reported success but provider did not return a reconstructable payload.",
        error_type="invalid_stream_error",
    )


def raise_task_timeout_error(request: RequestProtocol, timeout: float) -> NoReturn:
    raise_gateway_timeout(request, f"Request timed out after {timeout} seconds.")
