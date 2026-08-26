"""SoAI - Durable Chat input comparison variants [backend/features/chat/conversation_input_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.model_settings.normalization import resolve_execution_model_sequence
from core.validation.integers import is_non_negative_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ConversationInputVariant",
    "apply_conversation_input_variant",
    "resolve_conversation_input_variants",
)


@dataclass(frozen=True, slots=True)
class ConversationInputVariant:
    model_settings: JSONDict
    request_id: str
    assistant_at_ms: int
    assistant_turn_at_ms: int
    model_variant_index: int
    final_planned_variant: bool


def resolve_conversation_input_variants(
    input_record: JSONDict,
) -> tuple[ConversationInputVariant, ...]:
    model_settings_value = input_record.get("model_settings")
    request_id_value = input_record.get("request_id")
    assistant_at_value = input_record.get("assistant_at_ms")
    assistant_turn_at_value = input_record.get("assistant_turn_at_ms")
    if not isinstance(model_settings_value, dict):
        raise StateError("Conversation input model settings snapshot is unavailable.")
    if not isinstance(request_id_value, str) or not request_id_value.strip():
        raise StateError("Conversation input request id is unavailable.")
    if not is_non_negative_strict_int(assistant_at_value):
        raise StateError("Conversation input assistant timestamp is invalid.")
    if not is_non_negative_strict_int(assistant_turn_at_value):
        raise StateError("Conversation input assistant turn timestamp is invalid.")
    models = resolve_execution_model_sequence(model_settings_value)
    variants: list[ConversationInputVariant] = []
    for model_variant_index, model_id in enumerate(models):
        variant_settings = dict(model_settings_value)
        variant_settings["model"] = model_id
        variant_settings.pop("comparison_models", None)
        variants.append(
            ConversationInputVariant(
                model_settings=variant_settings,
                request_id=(
                    request_id_value
                    if len(models) == 1
                    else f"{request_id_value}:variant:{model_variant_index}"
                ),
                assistant_at_ms=int(assistant_at_value) + model_variant_index,
                assistant_turn_at_ms=int(assistant_turn_at_value),
                model_variant_index=model_variant_index,
                final_planned_variant=model_variant_index == len(models) - 1,
            ),
        )
    return tuple(variants)


def apply_conversation_input_variant(
    input_record: JSONDict,
    variant: ConversationInputVariant,
) -> JSONDict:
    return {
        **input_record,
        "model_settings": variant.model_settings,
        "request_id": variant.request_id,
        "assistant_at_ms": variant.assistant_at_ms,
        "assistant_turn_at_ms": variant.assistant_turn_at_ms,
        "model_variant_index": variant.model_variant_index,
        "final_planned_variant": variant.final_planned_variant,
    }
