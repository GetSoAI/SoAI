"""SoAI - Base plugin OpenAI capability payloads [backend/core/plugins/base_plugin_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.capability_taxonomy import (
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIImageFeature,
)
from core.openai.compatibility import normalize_openai_modalities_strict
from core.plugins.protocols import OpenAICapabilityPluginClassProtocol
from core.types.json import JSONDict, JSONValue

__all__ = ("build_openai_capabilities",)


def build_openai_capabilities(
    plugin_class: type[OpenAICapabilityPluginClassProtocol],
) -> JSONDict:
    result: JSONDict = {}
    endpoints: JSONDict = {
        OpenAIEndpoint.CHAT_COMPLETIONS.value: bool(plugin_class.SUPPORTS_CHAT_COMPLETIONS),
        OpenAIEndpoint.COMPLETIONS.value: bool(plugin_class.SUPPORTS_COMPLETIONS),
        OpenAIEndpoint.RESPONSES.value: bool(plugin_class.SUPPORTS_RESPONSES),
        OpenAIEndpoint.EMBEDDINGS.value: bool(plugin_class.SUPPORTS_EMBEDDINGS),
        OpenAIEndpoint.IMAGES.value: bool(plugin_class.SUPPORTS_IMAGES),
        OpenAIEndpoint.AUDIO_TRANSCRIPTIONS.value: bool(plugin_class.SUPPORTS_AUDIO_TRANSCRIPTIONS),
        OpenAIEndpoint.AUDIO_TRANSLATIONS.value: bool(plugin_class.SUPPORTS_AUDIO_TRANSLATIONS),
        OpenAIEndpoint.AUDIO_SPEECH.value: bool(plugin_class.SUPPORTS_AUDIO_SPEECH),
    }
    image_features: JSONDict = {
        OpenAIImageFeature.IMAGE_EDITS.value: bool(plugin_class.SUPPORTS_IMAGE_EDITS),
        OpenAIImageFeature.IMAGE_VARIATIONS.value: bool(plugin_class.SUPPORTS_IMAGE_VARIATIONS),
    }
    chat_features: JSONDict = {
        OpenAIChatFeature.VISION.value: bool(plugin_class.SUPPORTS_VISION),
        OpenAIChatFeature.INPUT_AUDIO.value: bool(plugin_class.SUPPORTS_INPUT_AUDIO),
        OpenAIChatFeature.TOOL_CALLING.value: bool(plugin_class.SUPPORTS_TOOL_CALLING),
        OpenAIChatFeature.PARALLEL_TOOL_CALLS.value: bool(
            plugin_class.SUPPORTS_PARALLEL_TOOL_CALLS,
        ),
        OpenAIChatFeature.STRUCTURED_OUTPUT.value: bool(plugin_class.SUPPORTS_STRUCTURED_OUTPUT),
        OpenAIChatFeature.JSON_SCHEMA.value: bool(plugin_class.SUPPORTS_JSON_SCHEMA),
    }
    for payload in (endpoints, image_features, chat_features):
        for name, flag in payload.items():
            result[name] = flag
    result["endpoints"] = endpoints
    result["image_features"] = image_features
    result["chat_features"] = chat_features
    modalities_payload: list[JSONValue] = []
    for modality in normalize_openai_modalities_strict(
        plugin_class.SUPPORTED_MODALITIES,
        field_name="SUPPORTED_MODALITIES",
    ):
        modalities_payload.append(modality)
    result["modalities"] = modalities_payload
    supports_responses = bool(plugin_class.SUPPORTS_RESPONSES)
    responses_features: JSONDict = {
        "create": supports_responses,
        "retrieve": bool(plugin_class.SUPPORTS_RESPONSES_RETRIEVE),
        "delete": bool(plugin_class.SUPPORTS_RESPONSES_DELETE),
        "cancel": bool(plugin_class.SUPPORTS_RESPONSES_CANCEL),
        "input_items": bool(plugin_class.SUPPORTS_RESPONSES_INPUT_ITEMS),
        "input_tokens": bool(plugin_class.SUPPORTS_RESPONSES_INPUT_TOKENS),
    }
    result["responses_features"] = responses_features
    return result
