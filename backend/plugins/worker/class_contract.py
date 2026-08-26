"""SoAI - Plugin worker class declaration contract checks [backend/plugins/worker/class_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect

from core.errors.exceptions import ValidationError
from core.plugins.base_plugin import BasePlugin
from plugins.manifest.class_field_contract import PLUGIN_REQUIRED_METADATA_FIELDS

__all__ = (
    "REQUIRED_OPENAI_CAPABILITY_FIELDS",
    "ensure_declared_openai_capability_flags",
    "ensure_declared_plugin_metadata",
)

REQUIRED_OPENAI_CAPABILITY_FIELDS: tuple[str, ...] = (
    "SUPPORTED_MODALITIES",
    "SUPPORTS_AUDIO_SPEECH",
    "SUPPORTS_AUDIO_TRANSCRIPTIONS",
    "SUPPORTS_AUDIO_TRANSLATIONS",
    "SUPPORTS_CHAT_COMPLETIONS",
    "SUPPORTS_COMPLETIONS",
    "SUPPORTS_EMBEDDINGS",
    "SUPPORTS_IMAGES",
    "SUPPORTS_IMAGE_EDITS",
    "SUPPORTS_IMAGE_VARIATIONS",
    "SUPPORTS_INPUT_AUDIO",
    "SUPPORTS_JSON_SCHEMA",
    "SUPPORTS_PARALLEL_TOOL_CALLS",
    "SUPPORTS_RESPONSES",
    "SUPPORTS_RESPONSES_CANCEL",
    "SUPPORTS_RESPONSES_DELETE",
    "SUPPORTS_RESPONSES_INPUT_ITEMS",
    "SUPPORTS_RESPONSES_INPUT_TOKENS",
    "SUPPORTS_RESPONSES_RETRIEVE",
    "SUPPORTS_STRUCTURED_OUTPUT",
    "SUPPORTS_TOOL_CALLING",
    "SUPPORTS_VISION",
)


def _collect_plugin_attribute_owners(plugin_class: type[BasePlugin]) -> dict[str, type[BasePlugin]]:
    owners: dict[str, type[BasePlugin]] = {}
    for attribute in inspect.classify_class_attrs(plugin_class):
        if issubclass(attribute.defining_class, BasePlugin):
            owners[attribute.name] = attribute.defining_class
    return owners


def ensure_declared_plugin_metadata(plugin_class: type[BasePlugin], *, plugin_name: str) -> None:
    attribute_owners = _collect_plugin_attribute_owners(plugin_class)
    missing = sorted(
        attr_name
        for attr_name in PLUGIN_REQUIRED_METADATA_FIELDS
        if attribute_owners.get(attr_name) is not plugin_class
    )
    if missing:
        raise ValidationError(
            f"Plugin '{plugin_name}' must explicitly declare metadata fields: {', '.join(missing)}.",
        )


def ensure_declared_openai_capability_flags(
    plugin_class: type[BasePlugin],
    *,
    plugin_name: str,
) -> None:
    attribute_owners = _collect_plugin_attribute_owners(plugin_class)
    missing = sorted(
        attr_name
        for attr_name in REQUIRED_OPENAI_CAPABILITY_FIELDS
        if attribute_owners.get(attr_name) is not plugin_class
    )
    if missing:
        raise ValidationError(
            f"Plugin '{plugin_name}' must explicitly declare OpenAI capability flags: {', '.join(missing)}.",
        )
