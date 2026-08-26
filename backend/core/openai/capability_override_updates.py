"""SoAI - OpenAI capability override mutation resolution [backend/core/openai/capability_override_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.capabilities import normalize_openai_capabilities
from core.openai.capability_checks import is_openai_capability_enabled
from core.openai.capability_taxonomy import OPENAI_CAPABILITY_CATEGORIES, OpenAIModality
from core.openai.effective_profile import (
    build_openai_capability_overrides_payload,
    normalize_openai_base_modalities,
    parse_openai_capability_overrides,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "OpenAICapabilityOverrideUpdate",
    "resolve_openai_capability_override_update",
)


@dataclass(frozen=True, slots=True)
class OpenAICapabilityOverrideUpdate:
    next_payload: JSONDict | None
    changed: bool


def resolve_openai_capability_override_update(
    *,
    base_modalities: JSONValue,
    base_openai_capabilities: JSONValue,
    current_overrides: JSONValue,
    category: str,
    token: str,
    enabled: bool,
    universal_id: str,
    plugin_name: str,
) -> OpenAICapabilityOverrideUpdate:
    normalized_category = str(category or "").strip().lower()
    normalized_token = str(token or "").strip().lower()
    if not normalized_category or not normalized_token:
        raise ValidationError("category and token are required.")
    normalized_base_modalities = _normalize_plugin_modalities(
        base_modalities,
        plugin_name=plugin_name,
    )
    base_caps = (
        normalize_openai_capabilities(base_openai_capabilities)
        if not isinstance(base_openai_capabilities, Mapping)
        else normalize_openai_capabilities(dict(base_openai_capabilities))
    )
    _validate_requested_override(
        category=normalized_category,
        token=normalized_token,
        base_modalities=normalized_base_modalities,
        base_caps=base_caps,
        plugin_name=plugin_name,
    )
    stored_disabled = parse_openai_capability_overrides(current_overrides)
    current_disabled = _filter_supported_openai_overrides(
        stored_disabled,
        base_modalities=normalized_base_modalities,
        base_caps=base_caps,
    )
    next_disabled = {
        category_key: set(token_set) for category_key, token_set in current_disabled.items()
    }
    category_disabled = next_disabled.get(normalized_category) or set()
    next_disabled[normalized_category] = category_disabled
    if enabled:
        category_disabled.discard(normalized_token)
    else:
        category_disabled.add(normalized_token)
    if not category_disabled:
        next_disabled.pop(normalized_category, None)
    stored_payload = build_openai_capability_overrides_payload(stored_disabled)
    next_payload = build_openai_capability_overrides_payload(next_disabled)
    _validate_effective_modalities(
        category=normalized_category,
        disabled_modalities=category_disabled,
        base_modalities=normalized_base_modalities,
        universal_id=universal_id,
    )
    return OpenAICapabilityOverrideUpdate(
        next_payload=next_payload,
        changed=stored_payload != next_payload,
    )


def _normalize_plugin_modalities(value: JSONValue, *, plugin_name: str) -> list[str]:
    message = f"Plugin '{plugin_name}' has invalid modalities metadata."
    return normalize_openai_base_modalities(
        value,
        invalid_collection_message=message,
        invalid_entry_message=message,
        empty_entry_message=message,
    )


def _validate_requested_override(
    *,
    category: str,
    token: str,
    base_modalities: Sequence[str],
    base_caps: JSONDict,
    plugin_name: str,
) -> None:
    if category == "modalities":
        if token == OpenAIModality.TEXT.value and token in base_modalities:
            raise ValidationError("The 'text' modality cannot be disabled.")
        if token not in base_modalities:
            raise ValidationError(f"Modality '{token}' is not supported by plugin '{plugin_name}'.")
        return
    if category in OPENAI_CAPABILITY_CATEGORIES:
        if not is_openai_capability_enabled(base_caps, category, token):
            raise ValidationError(
                f"Capability '{token}' is not supported by plugin '{plugin_name}'.",
            )
        return
    raise ValidationError(f"Unknown OpenAI capability category '{category}'.")


def _filter_supported_openai_overrides(
    disabled: Mapping[str, set[str]],
    *,
    base_modalities: Sequence[str],
    base_caps: JSONDict,
) -> dict[str, set[str]]:
    filtered: dict[str, set[str]] = {}
    base_modality_set = set(base_modalities)
    for category, tokens in disabled.items():
        supported_tokens = _filter_supported_override_tokens(
            category=category,
            tokens=tokens,
            base_modalities=base_modality_set,
            base_caps=base_caps,
        )
        if supported_tokens:
            filtered[category] = supported_tokens
    return filtered


def _filter_supported_override_tokens(
    *,
    category: str,
    tokens: set[str],
    base_modalities: set[str],
    base_caps: JSONDict,
) -> set[str]:
    if category == "modalities":
        return {
            token
            for token in tokens
            if token != OpenAIModality.TEXT.value and token in base_modalities
        }
    if category in OPENAI_CAPABILITY_CATEGORIES:
        return {
            token for token in tokens if is_openai_capability_enabled(base_caps, category, token)
        }
    return set()


def _validate_effective_modalities(
    *,
    category: str,
    disabled_modalities: set[str],
    base_modalities: Sequence[str],
    universal_id: str,
) -> None:
    if category != "modalities":
        return
    effective_modalities = [
        modality for modality in base_modalities if modality not in disabled_modalities
    ]
    if not effective_modalities:
        raise ValidationError(f"Model '{universal_id}' must have at least one effective modality.")
