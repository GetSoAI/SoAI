"""SoAI - Inference payload preparation for executor [backend/orchestrator/execution/payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.models.model_info_fields import coerce_plugin_name
from core.models.protocols import ModelInformationServiceProtocol
from core.models.source_identifier import resolve_source_model_id
from core.openai.capability_checks import (
    has_openai_modality,
    is_openai_audio_input_supported,
    is_openai_vision_input_supported,
)
from core.openai.capability_taxonomy import OpenAIModality
from core.openai.message_content_validation import validate_message_content_json
from core.openai.responses_input_modalities import (
    infer_required_modalities_from_responses_input,
)
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from core.types.json import is_json_value
from orchestrator.execution.dependencies import InferencePayloadPreparerDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("InferencePayloadPreparer",)


class InferencePayloadPreparer:
    def __init__(self, deps: InferencePayloadPreparerDependencies) -> None:
        self._queue: OrchestratorQueueProtocol = deps.queue
        self._model_information_service: ModelInformationServiceProtocol = (
            deps.model_information_service
        )

    async def resolve_modality_compatible_targets(
        self,
        required_modalities: tuple[str, ...],
        limit: int = 5,
    ) -> tuple[list[str], list[str]]:
        if not required_modalities:
            return ([], [])
        formatted = await self._model_information_service.model_get_formatted_list()
        compatible_models: list[str] = []
        compatible_plugins: set[str] = set()
        for plugin_key, models in formatted.items():
            if plugin_key in {"virtual", "orphaned"}:
                continue
            for entry in models:
                if entry.get("status") != "active":
                    continue
                if entry.get("is_available") is False:
                    continue
                if _supports_required_modalities(entry, required_modalities):
                    model_id = entry.get("id")
                    if isinstance(model_id, str) and model_id:
                        compatible_models.append(model_id)
                    plugin_name = coerce_plugin_name(entry)
                    if plugin_name is not None:
                        compatible_plugins.add(plugin_name)
        model_candidates = sorted(dict.fromkeys(compatible_models))
        plugin_candidates = sorted(compatible_plugins)
        return (model_candidates[:limit], plugin_candidates[:limit])

    async def prepare_inference_payload_for_plugin(
        self,
        task: Task,
        plugin_name: str,
        model_info: JSONDict | None,
    ) -> JSONDict:
        context = self._queue.require_orchestration_context(task)
        if not context.event:
            raise StateError("Missing inference event for task")
        payload = context.event.payload
        messages_value = payload.get("messages")
        input_value = payload.get("input")
        if (not isinstance(messages_value, list)) and (not isinstance(input_value, list)):
            return payload
        capability_profile: JSONDict
        if isinstance(model_info, dict):
            capability_profile = dict(model_info)
        else:
            capability_profile = (
                await self._model_information_service.model_get_plugin_capability_profile(
                    plugin_name,
                )
            )
        effective_modalities = _resolve_effective_modalities(capability_profile)
        supports_vision = is_openai_vision_input_supported(
            modalities=capability_profile.get("modalities"),
            openai_capabilities=capability_profile.get("openai_capabilities"),
        )
        supports_audio = is_openai_audio_input_supported(
            modalities=capability_profile.get("modalities"),
            openai_capabilities=capability_profile.get("openai_capabilities"),
        )
        is_text_only = not supports_vision and (not supports_audio)
        detected_modalities: set[str] = set()
        normalized_messages: list[JSONDict] = []
        changed = False
        if isinstance(messages_value, list):
            messages: list[JSONValue] = []
            for item in messages_value:
                messages.append(item)
            for index, message_value in enumerate(messages):
                if not isinstance(message_value, Mapping):
                    raise ValidationError(f"Message at index {index} must be an object.")
                message_json: JSONDict = {}
                for key, value in message_value.items():
                    if not isinstance(key, str):
                        raise ValidationError(
                            f"Message at index {index} contains a non-string key.",
                        )
                    if not is_json_value(value):
                        raise ValidationError(
                            f"Message at index {index} contains a non-JSON value.",
                        )
                    message_json[key] = value
                content = message_json.get("content")
                if isinstance(content, list):
                    validated_parts = validate_message_content_json(
                        content,
                        param_prefix=f"messages[{index}].content",
                    )
                    if not isinstance(validated_parts, list):
                        raise ValidationError("Message content must be an array.")
                    text_parts: list[str] = []
                    has_non_text = False
                    for part in validated_parts:
                        part_type = str(part.get("type", "")).strip().lower()
                        if part_type == "text":
                            text_value = part.get("text", "")
                            text_parts.append(str(text_value) if text_value else "")
                            continue
                        has_non_text = True
                        if part_type == "image_url":
                            detected_modalities.add(OpenAIModality.VISION.value)
                        elif part_type == "input_audio":
                            detected_modalities.add(OpenAIModality.AUDIO.value)
                    if has_non_text:
                        normalized_messages.append(message_json)
                        continue
                    if is_text_only:
                        combined = "\n".join([text for text in text_parts if text])
                        if not combined:
                            raise ValidationError(
                                f"Message content at index {index} must include text.",
                            )
                        new_message: JSONDict = dict(message_json)
                        new_message["content"] = combined
                        normalized_messages.append(new_message)
                        changed = True
                    else:
                        normalized_messages.append(message_json)
                    continue
                normalized_messages.append(message_json)
        elif isinstance(input_value, list):
            for modality in infer_required_modalities_from_responses_input(input_value):
                if modality == OpenAIModality.VISION.value:
                    detected_modalities.add(OpenAIModality.VISION.value)
                elif modality == OpenAIModality.AUDIO.value:
                    detected_modalities.add(OpenAIModality.AUDIO.value)
        missing_modalities: list[str] = []
        if OpenAIModality.VISION.value in detected_modalities and (not supports_vision):
            missing_modalities.append(OpenAIModality.VISION.value)
        if OpenAIModality.AUDIO.value in detected_modalities and (not supports_audio):
            missing_modalities.append(OpenAIModality.AUDIO.value)
        if missing_modalities:
            requested_model = payload.get("model")
            model_label = None
            if isinstance(model_info, dict):
                model_label = (
                    model_info.get("display_name")
                    or resolve_source_model_id(model_info)
                    or model_info.get("universal_id")
                )
            if not isinstance(model_label, str) or not model_label:
                model_label = (
                    requested_model
                    if isinstance(requested_model, str) and requested_model
                    else "unknown"
                )
            supported_modalities = effective_modalities or [OpenAIModality.TEXT.value]
            compatible_models, compatible_plugins = await self.resolve_modality_compatible_targets(
                tuple(sorted(detected_modalities)),
            )
            message_parts: list[str] = [
                f"Request contains modalities {', '.join(sorted(detected_modalities))}.",
                (
                    f"Selected model '{model_label}' on plugin '{plugin_name}' supports "
                    f"{', '.join(sorted(supported_modalities))}."
                ),
            ]
            if compatible_models:
                message_parts.append(f"Compatible models: {', '.join(compatible_models)}.")
            if compatible_plugins:
                message_parts.append(f"Compatible plugins: {', '.join(compatible_plugins)}.")
            message_parts.extend(_build_modality_fix_messages(tuple(sorted(missing_modalities))))
            raise ValidationError(" ".join(message_parts))
        if not changed:
            return payload
        updated_payload = dict(payload)
        updated_payload["messages"] = normalized_messages
        return updated_payload


def _resolve_effective_modalities(capability_profile: Mapping[str, JSONValue]) -> list[str]:
    modalities_value = capability_profile.get("modalities")
    if modalities_value is None:
        return [OpenAIModality.TEXT.value]
    if not isinstance(modalities_value, list):
        raise StateError("OpenAI capability profile modalities must be an array")
    effective_modalities: list[str] = []
    for item in modalities_value:
        if not isinstance(item, str):
            raise StateError("OpenAI capability profile contains non-string modality")
        if item:
            effective_modalities.append(item)
    if effective_modalities:
        return effective_modalities
    return [OpenAIModality.TEXT.value]


def _build_modality_fix_messages(missing_modalities: tuple[str, ...]) -> list[str]:
    messages: list[str] = []
    if OpenAIModality.VISION.value in missing_modalities:
        messages.append("This request contains image input, but the selected model is text-only.")
        messages.append(
            "Fix: select a model with vision support, remove the image, or disable image relay for this turn.",
        )
    if OpenAIModality.AUDIO.value in missing_modalities:
        messages.append(
            "This request contains audio input, but the selected model does not support audio input.",
        )
        messages.append("Fix: select a model with audio input support or remove the audio content.")
    if messages:
        return messages
    return ["Fix: select a compatible model or remove unsupported content parts."]


def _supports_required_modalities(
    capability_profile: Mapping[str, JSONValue],
    required_modalities: tuple[str, ...],
) -> bool:
    for modality in required_modalities:
        if modality == OpenAIModality.VISION.value:
            if not is_openai_vision_input_supported(
                modalities=capability_profile.get("modalities"),
                openai_capabilities=capability_profile.get("openai_capabilities"),
            ):
                return False
            continue
        if modality == OpenAIModality.AUDIO.value:
            if not is_openai_audio_input_supported(
                modalities=capability_profile.get("modalities"),
                openai_capabilities=capability_profile.get("openai_capabilities"),
            ):
                return False
            continue
        if not has_openai_modality(capability_profile.get("modalities"), modality):
            return False
    return True
