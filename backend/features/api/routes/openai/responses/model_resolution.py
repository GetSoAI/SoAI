"""SoAI - OpenAI Responses model resolution helper [backend/features/api/routes/openai/responses/model_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.request_fields import resolve_optional_model_name
from features.api.routes.openai.openai_default_model_resolution import (
    require_openai_default_model_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = ("resolve_responses_model_id_from_payload",)


async def resolve_responses_model_id_from_payload(
    *,
    api_context: ApiContext,
    payload_json: dict[str, JSONValue],
    trace_id: str,
) -> str:
    explicit_model = resolve_optional_model_name(payload_json)
    return await require_openai_default_model_id(
        api_context=api_context,
        explicit_model=explicit_model,
        required_openai_capability="responses",
        trace_id=trace_id,
        config_default_dotted_key=None,
    )
