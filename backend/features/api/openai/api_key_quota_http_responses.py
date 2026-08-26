"""SoAI - OpenAI API key quota HTTP responses [backend/features/api/openai/api_key_quota_http_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from core.timing.durations import ms_to_seconds_ceil
from core.validation.integers import is_strict_int
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_insufficient_quota_response",)


def build_insufficient_quota_response(
    *,
    trace_id: str | None,
    window: str,
    retry_at_ms: int,
    now_ts_ms: int,
    status: JSONDict | None,
) -> JSONResponse:
    retry_after_ms = max(0, int(retry_at_ms) - int(now_ts_ms))
    retry_after_seconds = ms_to_seconds_ceil(retry_after_ms)
    message = f"Quota exceeded for {window}."
    response = build_openai_error_json_response_for_status(
        status_code=429,
        message=message,
        soai_code="insufficient_quota",
        param=None,
        trace_id=trace_id,
    )
    response.headers["Retry-After"] = str(retry_after_seconds)
    response.headers["X-RateLimit-Reset"] = str(ms_to_seconds_ceil(int(retry_at_ms)))
    if status is not None:
        window_status_value = status.get(window)
        window_status = window_status_value if isinstance(window_status_value, dict) else None
        if window_status is not None:
            limit_value = window_status.get("limit_units")
            remaining_value = window_status.get("remaining_units")
            if is_strict_int(limit_value):
                response.headers["X-RateLimit-Limit"] = str(int(limit_value))
            if is_strict_int(remaining_value):
                response.headers["X-RateLimit-Remaining"] = str(int(remaining_value))
    return response
