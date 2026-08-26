"""SoAI - Internal OpenAI request field filtering [backend/core/openai/request_field_filtering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.request_send_controls import apply_request_send_controls
from core.types.json_value import copy_json_dict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_inference_request_payload",)


def build_inference_request_payload(request_json: JSONDict) -> JSONDict:
    payload = copy_json_dict(request_json)
    payload.pop("conv_id", None)
    payload.pop("mcp", None)
    payload.pop("responses_api", None)
    apply_request_send_controls(payload)
    max_tokens_value = payload.get("max_tokens")
    if max_tokens_value is None:
        payload.pop("max_tokens", None)
    elif not is_strict_int(max_tokens_value) or int(max_tokens_value) < 0:
        raise ValidationError("max_tokens must be a non-negative integer.")
    max_completion_tokens_value = payload.get("max_completion_tokens")
    if max_completion_tokens_value is None:
        payload.pop("max_completion_tokens", None)
    elif not is_strict_int(max_completion_tokens_value) or int(max_completion_tokens_value) < 0:
        raise ValidationError("max_completion_tokens must be a non-negative integer.")
    max_output_tokens_value = payload.get("max_output_tokens")
    if max_output_tokens_value is None:
        payload.pop("max_output_tokens", None)
    elif not is_strict_int(max_output_tokens_value) or int(max_output_tokens_value) < 0:
        raise ValidationError("max_output_tokens must be a non-negative integer.")
    return payload
