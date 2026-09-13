"""SoAI - OpenAI Responses create request validation helpers [backend/features/api/routes/openai/responses/create_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from pydantic import ValidationError

from core.openai.capability_requirements import infer_responses_capability_requirements
from core.openai.responses_input_modalities import (
    infer_required_modalities_from_responses_input,
)
from features.api.runtime.openai_request_validation import (
    build_openai_invalid_request_response,
)
from features.api.schemas.openai_responses import ResponsesRequest

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "infer_required_capabilities",
    "infer_required_modalities",
    "validate_responses_create_payload_or_response",
)


def validate_responses_create_payload_or_response(
    payload_json: dict[str, JSONValue],
    *,
    trace_id: str,
) -> dict[str, JSONValue] | JSONResponse:
    try:
        validated = ResponsesRequest.model_validate(payload_json)
    except ValidationError:
        return build_openai_invalid_request_response(
            message="Invalid Responses request. Check field names and value types, then retry.",
            param=None,
            trace_id=trace_id,
            code="invalid_request_error",
        )
    return dict(validated.model_dump(exclude_none=True))


def infer_required_modalities(payload_json: dict[str, JSONValue]) -> tuple[str, ...]:
    return infer_required_modalities_from_responses_input(payload_json.get("input"))


def infer_required_capabilities(payload_json: dict[str, JSONValue]) -> tuple[str, ...]:
    return infer_responses_capability_requirements(payload_json)
