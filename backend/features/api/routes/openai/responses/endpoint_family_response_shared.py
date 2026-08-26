"""SoAI - Shared response endpoint validation helpers [backend/features/api/routes/openai/responses/endpoint_family_response_shared.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import Response

from features.api.openai.openai_error_responses import (
    build_openai_error_json_response,
    build_openai_invalid_request_json_response,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.types.json import JSONValue

__all__ = (
    "create_response_not_found_error",
    "create_response_server_error",
    "create_response_not_stored_error",
    "normalize_response_id_or_error",
    "response_record_flag_enabled",
)


def normalize_response_id_or_error(
    response_id: str,
    *,
    trace_id: str,
    param_name: str = "response_id",
) -> tuple[str, Response | None]:
    normalized_response_id = response_id.strip()
    if not normalized_response_id:
        return (
            "",
            build_openai_invalid_request_json_response(
                message="response_id is required.",
                param=param_name,
                trace_id=trace_id,
            ),
        )
    return (normalized_response_id, None)


def create_response_not_found_error(*, trace_id: str, param_name: str = "response_id") -> Response:
    return build_openai_invalid_request_json_response(
        status_code=404,
        message="Response not found.",
        param=param_name,
        trace_id=trace_id,
    )


def create_response_not_stored_error(*, trace_id: str, param_name: str = "response_id") -> Response:
    return build_openai_invalid_request_json_response(
        status_code=404,
        message="Response was not stored.",
        param=param_name,
        trace_id=trace_id,
    )


def create_response_server_error(*, trace_id: str, message: str) -> Response:
    return build_openai_error_json_response(
        status_code=502,
        message=message,
        canonical_error_type="server_error",
        param=None,
        code=None,
        trace_id=trace_id,
        headers=None,
    )


def response_record_flag_enabled(record: Mapping[str, JSONValue], field_name: str) -> bool:
    value = record.get(field_name)
    return (int(value) if isinstance(value, int) else 0) == 1
