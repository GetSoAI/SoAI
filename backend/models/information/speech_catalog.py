"""SoAI - Speech-to-text plugin and model catalog snapshots [backend/models/information/speech_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.media.speech_catalog import (
    SpeechCatalogSnapshot,
    SpeechModelEntry,
    SpeechPluginEntry,
)
from core.models.parameter_request_overrides import is_request_overridable_parameter
from core.models.parameter_schema_contract import validate_parameter_value
from core.models.protocols import ModelInformationServiceProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.openai.capability_checks import is_openai_capability_enabled
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONDict
from core.validation.booleans import parse_bool_flag_with_default
from core.validation.strings import coerce_optional_trimmed_str
from models.manager.capabilities import normalize_openai_capabilities_value

__all__ = ("SpeechCatalogService", "SpeechCatalogServiceDependencies")


@dataclass(frozen=True, slots=True)
class SpeechCatalogServiceDependencies:
    database_plugins: DatabasePluginsProtocol
    database_models: DatabaseModelsProtocol
    model_information_service: ModelInformationServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SpeechCatalogServiceDependencies",
            database_plugins=self.database_plugins,
            database_models=self.database_models,
            model_information_service=self.model_information_service,
        )


def _speech_plugin_entry(record: JSONDict) -> SpeechPluginEntry | None:
    plugin_name = coerce_optional_trimmed_str(record.get("plugin_name"))
    if plugin_name is None:
        return None
    capabilities = normalize_openai_capabilities_value(record.get("openai_capabilities"))
    transcription = is_openai_capability_enabled(capabilities, "endpoints", "audio_transcriptions")
    translation = is_openai_capability_enabled(capabilities, "endpoints", "audio_translations")
    if not transcription and not translation:
        return None
    return SpeechPluginEntry(
        plugin_name=plugin_name,
        display_name=coerce_optional_trimmed_str(record.get("name")) or plugin_name,
        state=coerce_optional_trimmed_str(record.get("state")) or "",
        local_models=parse_bool_flag_with_default(record.get("local_models"), default=False),
        transcription=transcription,
        translation=translation,
        supports_backend_installation=parse_bool_flag_with_default(
            record.get("supports_backend_installation"),
            default=False,
        ),
        supports_model_download=parse_bool_flag_with_default(
            record.get("supports_model_download"),
            default=False,
        ),
        decoding_parameters=_decoding_parameters(record),
    )


def _decoding_parameters(record: JSONDict) -> JSONDict:
    raw_schema = record.get("parameter_schema")
    schema = (
        parse_json_dict(raw_schema, field="Speech parameter schema")
        if isinstance(raw_schema, str)
        else raw_schema
    )
    if not isinstance(schema, dict):
        return {}
    definitions = schema.get("parameters")
    protocol_fields = schema.get("protocol_fields")
    selected: JSONDict = {}
    for name, value in (("temperature", 0.0), ("condition_on_previous_text", False)):
        definition = definitions.get(name) if isinstance(definitions, dict) else None
        if isinstance(definition, dict) and is_request_overridable_parameter(definition):
            try:
                validate_parameter_value(definition=definition, value=value, label=name)
            except ValidationError:
                continue
            selected[name] = value
        elif name == "temperature" and isinstance(protocol_fields, dict):
            protocol = protocol_fields.get(name)
            if isinstance(protocol, dict) and protocol.get("support") == "implemented":
                selected[name] = value
    return selected


class SpeechCatalogService:
    def __init__(self, deps: SpeechCatalogServiceDependencies) -> None:
        self._database_plugins = deps.database_plugins
        self._database_models = deps.database_models
        self._model_information_service = deps.model_information_service

    async def snapshot_speech_catalog(self) -> SpeechCatalogSnapshot:
        plugins = tuple(
            sorted(
                (
                    entry
                    for record in await self._database_plugins.get_all_plugins()
                    if (entry := _speech_plugin_entry(record)) is not None
                ),
                key=lambda entry: entry.plugin_name,
            ),
        )
        local_plugin_names = {plugin.plugin_name for plugin in plugins if plugin.local_models}
        if not local_plugin_names:
            return SpeechCatalogSnapshot(plugins=plugins, models=())
        models_by_plugin = await self._database_models.get_all_models_by_plugin()
        universal_ids = sorted(
            universal_id
            for plugin_name in local_plugin_names
            for model in models_by_plugin.get(plugin_name, {}).values()
            if (universal_id := coerce_optional_trimmed_str(model.get("universal_id")))
        )
        if not universal_ids:
            return SpeechCatalogSnapshot(plugins=plugins, models=())
        records = await self._model_information_service.model_get_info_batch(universal_ids)
        models = tuple(
            SpeechModelEntry(universal_id=universal_id, plugin_name=plugin_name, model_info=record)
            for universal_id in universal_ids
            if (record := records.get(universal_id)) is not None
            and (plugin_name := coerce_optional_trimmed_str(record.get("plugin"))) is not None
            and plugin_name in local_plugin_names
        )
        return SpeechCatalogSnapshot(plugins=plugins, models=models)
