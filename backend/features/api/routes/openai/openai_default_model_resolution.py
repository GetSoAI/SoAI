"""SoAI - OpenAI endpoint default model resolution [backend/features/api/routes/openai/openai_default_model_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext

__all__ = (
    "require_openai_default_model_id",
    "resolve_openai_default_model_id",
)


async def resolve_openai_default_model_id(
    *,
    api_context: ApiContext,
    explicit_model: str | None,
    required_openai_capability: str,
    trace_id: str | None,
    config_default_dotted_key: str | None,
    model_id_predicate: Callable[[str], bool] | None = None,
) -> str | None:
    normalized_explicit = coerce_optional_trimmed_str(explicit_model)
    if normalized_explicit is not None:
        return normalized_explicit
    config_default: str | None = None
    if isinstance(config_default_dotted_key, str) and config_default_dotted_key.strip():
        config_default_value = api_context.dependencies.config.get_str(config_default_dotted_key)
        config_default = coerce_optional_trimmed_str(config_default_value)
    if config_default is not None:
        details = (
            await api_context.dependencies.model_information_service.model_get_openai_formatted(
                config_default,
                api_context.dependencies.model_resolution_service.model_resolve_to_universal_id,
            )
        )
        if not isinstance(details, dict):
            raise ValidationError(
                f"{config_default_dotted_key} is set, but the model could not be resolved.",
                details={"param": "model"},
                trace_id=trace_id,
            )
        capabilities = details.get("openai_capabilities")
        if not isinstance(capabilities, dict) or not bool(
            capabilities.get(required_openai_capability),
        ):
            raise ValidationError(
                f"{config_default_dotted_key} does not support the requested OpenAI operation.",
                details={"param": "model"},
                trace_id=trace_id,
            )
        if model_id_predicate is not None and not model_id_predicate(config_default):
            raise ValidationError(
                f"{config_default_dotted_key} does not match the requested model family.",
                details={"param": "model"},
                trace_id=trace_id,
            )
        return config_default
    candidates = await api_context.dependencies.model_information_service.model_get_available()
    matching: list[str] = []
    for entry in candidates:
        model_id = entry.get("id")
        normalized_model_id = coerce_optional_trimmed_str(
            model_id if isinstance(model_id, str) else None,
        )
        if normalized_model_id is None:
            continue
        capabilities = entry.get("openai_capabilities")
        if not isinstance(capabilities, dict):
            continue
        if bool(capabilities.get(required_openai_capability)):
            if model_id_predicate is not None and not model_id_predicate(normalized_model_id):
                continue
            matching.append(normalized_model_id)
    if not matching:
        return None
    return sorted(dict.fromkeys(matching))[0]


async def require_openai_default_model_id(
    *,
    api_context: ApiContext,
    explicit_model: str | None,
    required_openai_capability: str,
    trace_id: str | None,
    config_default_dotted_key: str | None,
    model_id_predicate: Callable[[str], bool] | None = None,
) -> str:
    resolved = await resolve_openai_default_model_id(
        api_context=api_context,
        explicit_model=explicit_model,
        required_openai_capability=required_openai_capability,
        trace_id=trace_id,
        config_default_dotted_key=config_default_dotted_key,
        model_id_predicate=model_id_predicate,
    )
    if resolved is None:
        raise ValidationError(
            "No compatible model is available for this request.",
            details={"param": "model"},
            trace_id=trace_id,
        )
    return resolved
