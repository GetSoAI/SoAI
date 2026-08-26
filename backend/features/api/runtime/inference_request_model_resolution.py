"""SoAI - Inference request model resolution [backend/features/api/runtime/inference_request_model_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.request_fields import resolve_optional_model_name
from core.runtime.request_context import RequestContext
from core.runtime.request_context_agent_fields import read_agent_requested_model
from core.types.json_value import copy_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "EffectiveInferenceModelResolution",
    "require_effective_inference_model_id",
    "resolve_effective_inference_model_resolution",
)


@dataclass(frozen=True, slots=True)
class EffectiveInferenceModelResolution:
    effective_model_id: str | None
    request_json: JSONDict
    override_model_id: str | None
    original_model_id: str | None
    model_overridden: bool


def resolve_effective_inference_model_resolution(
    *,
    request_json: JSONDict,
    request_context: RequestContext,
    prepared_agent_request: PreparedExecutionRequest | None,
    apply_to_request_json: bool,
) -> EffectiveInferenceModelResolution:
    original_model_id = resolve_optional_model_name(request_json)
    override_model_id = (
        coerce_optional_trimmed_str(prepared_agent_request.requested_model)
        if prepared_agent_request is not None
        else None
    )
    if override_model_id is None:
        override_model_id = read_agent_requested_model(context=request_context)
    effective_model_id = override_model_id or original_model_id
    effective_request_json = request_json
    model_overridden = False
    if (
        apply_to_request_json
        and override_model_id is not None
        and override_model_id != original_model_id
    ):
        effective_request_json = copy_json_dict(request_json)
        effective_request_json["model"] = override_model_id
        model_overridden = True
    return EffectiveInferenceModelResolution(
        effective_model_id=effective_model_id,
        request_json=effective_request_json,
        override_model_id=override_model_id,
        original_model_id=original_model_id,
        model_overridden=model_overridden,
    )


def require_effective_inference_model_id(
    *,
    resolution: EffectiveInferenceModelResolution,
    error_message: str,
) -> str:
    model_id = resolution.effective_model_id
    if model_id is None:
        raise ValidationError(error_message)
    return model_id
