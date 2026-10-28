"""SoAI - Local speech-to-text model selection policy [backend/core/media/speech_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from core.media.speech_setup import (
    SpeechSetupReason,
    SpeechTask,
    build_speech_setup_error,
    plugin_backend_missing,
    plugin_disabled,
    plugin_serves_task,
    speech_task_endpoint,
)
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.models.provider_backing import is_provider_backed_model
from core.openai.audio_model_selection import is_auto_audio_model_selector
from core.openai.capability_checks import is_openai_model_capability_enabled
from core.types.json import JSONValue
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.media.speech_catalog import (
        SpeechCatalogSnapshot,
        SpeechModelEntry,
        SpeechPluginEntry,
    )
    from core.models.reference_resolution import ResolvedModelReference
    from core.types.json import JSONDict

__all__ = (
    "LEGACY_WHISPER_SIZE_IDENTITIES",
    "ResolvedSpeechModel",
    "SpeechModelSelector",
    "SpeechSelectorType",
    "is_eligible_speech_model",
    "parse_speech_model_selector",
    "select_speech_model",
)

LEGACY_WHISPER_SIZE_IDENTITIES = (
    ("tiny", "tiny"),
    ("base", "base"),
    ("small", "small"),
    ("medium", "medium"),
    ("large", "large-v3"),
    ("large-v2", "large-v2"),
    ("large-v3", "large-v3"),
)
_WHISPER_FAMILY = "whisper"
_LOCAL_MODEL_TYPE = "local"


class SpeechSelectorType(StrEnum):
    AUTO = "auto"
    LEGACY_SIZE = "legacy_size"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class SpeechModelSelector:
    type: SpeechSelectorType
    value: str


@dataclass(frozen=True, slots=True)
class ResolvedSpeechModel:
    universal_id: str
    plugin_name: str
    label: str
    decoding_parameters: JSONDict = field(default_factory=dict[str, JSONValue])


def parse_speech_model_selector(value: str) -> SpeechModelSelector:
    normalized = value.strip()
    if not normalized or is_auto_audio_model_selector(normalized):
        return SpeechModelSelector(type=SpeechSelectorType.AUTO, value="auto")
    if normalized in dict(LEGACY_WHISPER_SIZE_IDENTITIES):
        return SpeechModelSelector(type=SpeechSelectorType.LEGACY_SIZE, value=normalized)
    return SpeechModelSelector(type=SpeechSelectorType.REFERENCE, value=normalized)


def _is_local_record(model_info: JSONDict) -> bool:
    return not is_provider_backed_model(model_info) and model_info.get("type") == _LOCAL_MODEL_TYPE


def is_eligible_speech_model(
    model: SpeechModelEntry,
    plugin: SpeechPluginEntry,
    task: SpeechTask,
) -> bool:
    return (
        plugin_serves_task(plugin, task)
        and not plugin_disabled(plugin)
        and not plugin_backend_missing(plugin)
        and _is_local_record(model.model_info)
        and is_model_info_active_and_enabled(model.model_info)
        and is_openai_model_capability_enabled(
            model.model_info,
            category="endpoints",
            token=speech_task_endpoint(task),
        )
    )


def _resolved(model: SpeechModelEntry, plugin: SpeechPluginEntry) -> ResolvedSpeechModel:
    info = model.model_info
    label = (
        coerce_optional_trimmed_str(info.get("display_name"))
        or coerce_optional_trimmed_str(info.get("source_model_id"))
        or model.universal_id
    )
    return ResolvedSpeechModel(
        universal_id=model.universal_id,
        plugin_name=model.plugin_name,
        label=label,
        decoding_parameters=dict(plugin.decoding_parameters),
    )


def _plugins_by_name(snapshot: SpeechCatalogSnapshot) -> dict[str, SpeechPluginEntry]:
    return {plugin.plugin_name: plugin for plugin in snapshot.plugins}


def _first_eligible(
    models: list[SpeechModelEntry],
    plugins: Mapping[str, SpeechPluginEntry],
    task: SpeechTask,
) -> ResolvedSpeechModel | None:
    eligible = sorted(
        (
            model
            for model in models
            if (plugin := plugins.get(model.plugin_name)) is not None
            and is_eligible_speech_model(model, plugin, task)
        ),
        key=lambda model: model.universal_id,
    )
    return _resolved(eligible[0], plugins[eligible[0].plugin_name]) if eligible else None


def _blocked_model_reason(
    model_info: JSONDict,
    plugin: SpeechPluginEntry | None,
    task: SpeechTask,
) -> SpeechSetupReason:
    if not _is_local_record(model_info) or plugin is None or not plugin.local_models:
        return SpeechSetupReason.NOT_LOCAL
    if plugin_disabled(plugin):
        return SpeechSetupReason.PLUGIN_DISABLED
    if plugin_backend_missing(plugin):
        return SpeechSetupReason.BACKEND_NOT_INSTALLED
    if not plugin_serves_task(plugin, SpeechTask.TRANSCRIBE):
        return SpeechSetupReason.CONFIGURED_MODEL_MISSING
    if not is_model_info_active_and_enabled(model_info):
        return SpeechSetupReason.MODEL_DISABLED
    if task is SpeechTask.TRANSLATE:
        return SpeechSetupReason.TRANSLATION_UNSUPPORTED
    return SpeechSetupReason.CONFIGURED_MODEL_MISSING


def _plugin_stage(
    plugin: SpeechPluginEntry,
    models: list[SpeechModelEntry],
    task: SpeechTask,
) -> SpeechSetupReason:
    if plugin_disabled(plugin):
        return SpeechSetupReason.PLUGIN_DISABLED
    if plugin_backend_missing(plugin):
        return SpeechSetupReason.BACKEND_NOT_INSTALLED
    local_models = [
        model
        for model in models
        if model.plugin_name == plugin.plugin_name and _is_local_record(model.model_info)
    ]
    for endpoint_task in (task, SpeechTask.TRANSCRIBE):
        endpoint = speech_task_endpoint(endpoint_task)
        capable = [
            model
            for model in local_models
            if is_openai_model_capability_enabled(
                model.model_info,
                category="endpoints",
                token=endpoint,
            )
        ]
        if not capable:
            continue
        if endpoint_task is not task:
            enabled = any(is_model_info_active_and_enabled(model.model_info) for model in capable)
            return (
                SpeechSetupReason.TRANSLATION_UNSUPPORTED
                if enabled
                else SpeechSetupReason.MODEL_DISABLED
            )
        return SpeechSetupReason.MODEL_DISABLED
    return SpeechSetupReason.NO_MODEL_INSTALLED


_STAGE_PRECEDENCE: Final[tuple[SpeechSetupReason, ...]] = (
    SpeechSetupReason.MODEL_DISABLED,
    SpeechSetupReason.TRANSLATION_UNSUPPORTED,
    SpeechSetupReason.NO_MODEL_INSTALLED,
    SpeechSetupReason.PLUGIN_DISABLED,
    SpeechSetupReason.BACKEND_NOT_INSTALLED,
)


def _auto_reason(snapshot: SpeechCatalogSnapshot, task: SpeechTask) -> SpeechSetupReason:
    present = [
        plugin for plugin in snapshot.plugins if plugin_serves_task(plugin, SpeechTask.TRANSCRIBE)
    ]
    if not present:
        return SpeechSetupReason.NO_STT_PLUGIN
    models = list(snapshot.models)
    stages = {_plugin_stage(plugin, models, task) for plugin in present}
    if task is SpeechTask.TRANSLATE and not any(
        plugin_serves_task(plugin, task) for plugin in present
    ):
        stages = {
            (
                SpeechSetupReason.TRANSLATION_UNSUPPORTED
                if stage in {SpeechSetupReason.NO_MODEL_INSTALLED, SpeechSetupReason.MODEL_DISABLED}
                else stage
            )
            for stage in stages
        }
    for reason in _STAGE_PRECEDENCE:
        if reason in stages:
            return reason
    return SpeechSetupReason.NO_MODEL_INSTALLED


def _legacy_size_matches(model: SpeechModelEntry, identity: str) -> bool:
    info = model.model_info
    family = coerce_optional_trimmed_str(info.get("family"))
    if family is None or family.casefold() != _WHISPER_FAMILY:
        return False
    return identity in {
        coerce_optional_trimmed_str(info.get("source_model_id")),
        coerce_optional_trimmed_str(info.get("whisper_model_id")),
    }


def _select_legacy_size(
    snapshot: SpeechCatalogSnapshot,
    selector: SpeechModelSelector,
    task: SpeechTask,
) -> ResolvedSpeechModel:
    identity = dict(LEGACY_WHISPER_SIZE_IDENTITIES)[selector.value]
    plugins = _plugins_by_name(snapshot)
    matches = [model for model in snapshot.models if _legacy_size_matches(model, identity)]
    selected = _first_eligible(matches, plugins, task)
    if selected is not None:
        return selected
    if not matches:
        reason = SpeechSetupReason.CONFIGURED_MODEL_MISSING
    else:
        first_match = min(matches, key=lambda model: model.universal_id)
        reason = _blocked_model_reason(
            first_match.model_info,
            plugins.get(first_match.plugin_name),
            task,
        )
    raise build_speech_setup_error(reason, plugins=snapshot.plugins, selector=selector.value)


def _select_reference(
    snapshot: SpeechCatalogSnapshot,
    selector: SpeechModelSelector,
    task: SpeechTask,
    reference: ResolvedModelReference | None,
    reference_record: JSONDict | None,
) -> ResolvedSpeechModel:
    if reference is not None and reference.is_virtual:
        reason = SpeechSetupReason.NOT_LOCAL
    elif reference is None or reference_record is None or len(reference.universal_ids) != 1:
        reason = SpeechSetupReason.CONFIGURED_MODEL_MISSING
    else:
        universal_id = reference.universal_ids[0]
        plugin_name = coerce_optional_trimmed_str(reference_record.get("plugin")) or ""
        plugin = _plugins_by_name(snapshot).get(plugin_name)
        model = next(
            (entry for entry in snapshot.models if entry.universal_id == universal_id),
            None,
        )
        if (
            model is not None
            and plugin is not None
            and is_eligible_speech_model(model, plugin, task)
        ):
            return _resolved(model, plugin)
        reason = _blocked_model_reason(reference_record, plugin, task)
    raise build_speech_setup_error(reason, plugins=snapshot.plugins, selector=selector.value)


def select_speech_model(
    snapshot: SpeechCatalogSnapshot,
    *,
    selector: SpeechModelSelector,
    task: SpeechTask,
    reference: ResolvedModelReference | None = None,
    reference_record: JSONDict | None = None,
) -> ResolvedSpeechModel:
    if selector.type is SpeechSelectorType.LEGACY_SIZE:
        return _select_legacy_size(snapshot, selector, task)
    if selector.type is SpeechSelectorType.REFERENCE:
        return _select_reference(snapshot, selector, task, reference, reference_record)
    selected = _first_eligible(list(snapshot.models), _plugins_by_name(snapshot), task)
    if selected is not None:
        return selected
    raise build_speech_setup_error(
        _auto_reason(snapshot, task),
        plugins=snapshot.plugins,
        selector=None,
    )
