"""SoAI - Speech-to-text setup diagnosis from plugin declarations [backend/core/media/speech_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from core.media.speech_errors import SETUP_CANDIDATES_DETAIL_KEY, build_speech_unavailable_error
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
)

if TYPE_CHECKING:
    from core.media.speech_catalog import SpeechPluginEntry
    from core.media.speech_errors import SpeechToTextUnavailableError
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SpeechSetupReason",
    "SpeechTask",
    "build_speech_setup_error",
    "is_present_speech_plugin",
    "plugin_backend_missing",
    "plugin_disabled",
    "plugin_serves_task",
    "speech_task_endpoint",
)

_BACKEND_MISSING_STATES = frozenset(
    {PLUGIN_STATE_BACKEND_NOT_INSTALLED, PLUGIN_STATE_INSTALL_ERROR}
)
_NOT_PRESENT_STATES = frozenset(
    {
        PLUGIN_STATE_ABSENT,
        PLUGIN_STATE_DELETING,
        PLUGIN_STATE_INCOMPATIBLE,
        PLUGIN_STATE_NOT_DETECTED,
    },
)
_SELECTOR_ECHO_MAX_CHARS = 200


class SpeechTask(StrEnum):
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"


class SpeechSetupReason(StrEnum):
    NO_STT_PLUGIN = "no_stt_plugin"
    BACKEND_NOT_INSTALLED = "backend_not_installed"
    PLUGIN_DISABLED = "plugin_disabled"
    NO_MODEL_INSTALLED = "no_model_installed"
    MODEL_DISABLED = "model_disabled"
    CONFIGURED_MODEL_MISSING = "configured_model_missing"
    NOT_LOCAL = "not_local"
    TRANSLATION_UNSUPPORTED = "translation_unsupported"


def speech_task_endpoint(task: SpeechTask) -> str:
    if task is SpeechTask.TRANSLATE:
        return "audio_translations"
    return "audio_transcriptions"


def plugin_disabled(plugin: SpeechPluginEntry) -> bool:
    return plugin.state == ORCH_STATE_DISABLED


def plugin_backend_missing(plugin: SpeechPluginEntry) -> bool:
    return plugin.state in _BACKEND_MISSING_STATES


def is_present_speech_plugin(plugin: SpeechPluginEntry) -> bool:
    return plugin.local_models and plugin.transcription and plugin.state not in _NOT_PRESENT_STATES


def plugin_serves_task(plugin: SpeechPluginEntry, task: SpeechTask) -> bool:
    if task is SpeechTask.TRANSLATE:
        return (
            plugin.local_models and plugin.translation and plugin.state not in _NOT_PRESENT_STATES
        )
    return is_present_speech_plugin(plugin)


def _setup_candidate(plugin: SpeechPluginEntry) -> JSONDict:
    setup_blocked = plugin_disabled(plugin) or plugin_backend_missing(plugin)
    return {
        "plugin_name": plugin.plugin_name,
        "display_name": plugin.display_name,
        "state": plugin.state,
        "backend_installable": plugin.supports_backend_installation
        and plugin_backend_missing(plugin),
        "models_downloadable": plugin.supports_model_download and not setup_blocked,
        "enable_required": plugin_disabled(plugin),
    }


def _joined_names(plugins: tuple[SpeechPluginEntry, ...]) -> str:
    return ", ".join(plugin.display_name for plugin in plugins)


def _message(reason: SpeechSetupReason, plugins: tuple[SpeechPluginEntry, ...]) -> str:
    names = _joined_names(plugins)
    if reason is SpeechSetupReason.NO_STT_PLUGIN:
        return "No installed plugin provides local speech-to-text. Add one on the Plugins page."
    if reason is SpeechSetupReason.BACKEND_NOT_INSTALLED:
        verb = "provides" if len(plugins) == 1 else "provide"
        return (
            f"Speech-to-text needs a local backend and model. {names} {verb} it: "
            "install its backend, then download a model. "
            "Smaller models are faster; larger ones are more accurate."
        )
    if reason is SpeechSetupReason.PLUGIN_DISABLED:
        return (
            f"Speech-to-text needs a local backend and model. Enable {names} on the Plugins page."
        )
    if reason is SpeechSetupReason.NO_MODEL_INSTALLED:
        return (
            "Speech-to-text needs a local model. " f"Download a {names} model on the Models page."
        )
    if reason is SpeechSetupReason.MODEL_DISABLED:
        return "All local speech-to-text models are disabled. Enable one on the Models page."
    if reason is SpeechSetupReason.CONFIGURED_MODEL_MISSING:
        return (
            "The selected speech model is not installed. "
            "Download it or change the speech model setting."
        )
    if reason is SpeechSetupReason.NOT_LOCAL:
        return "Media transcription runs locally. Choose a local speech-to-text model."
    return (
        "No installed local speech model supports translation. "
        "Download a multilingual model or change the speech model setting."
    )


def build_speech_setup_error(
    reason: SpeechSetupReason,
    *,
    plugins: tuple[SpeechPluginEntry, ...],
    selector: str | None,
) -> SpeechToTextUnavailableError:
    candidates = tuple(
        sorted(
            (plugin for plugin in plugins if is_present_speech_plugin(plugin)),
            key=lambda plugin: plugin.plugin_name,
        ),
    )
    setup: list[JSONValue] = [_setup_candidate(plugin) for plugin in candidates]
    details: JSONDict = {"reason": reason.value, SETUP_CANDIDATES_DETAIL_KEY: setup}
    if selector is not None:
        details["selector"] = selector[:_SELECTOR_ECHO_MAX_CHARS]
    return build_speech_unavailable_error(
        _message(reason, _reason_plugins(reason, candidates)),
        reason=reason.value,
        public_details=details,
    )


def _reason_plugins(
    reason: SpeechSetupReason,
    candidates: tuple[SpeechPluginEntry, ...],
) -> tuple[SpeechPluginEntry, ...]:
    if reason is SpeechSetupReason.BACKEND_NOT_INSTALLED:
        matching = tuple(plugin for plugin in candidates if plugin_backend_missing(plugin))
    elif reason is SpeechSetupReason.PLUGIN_DISABLED:
        matching = tuple(plugin for plugin in candidates if plugin_disabled(plugin))
    else:
        matching = tuple(
            plugin
            for plugin in candidates
            if not plugin_disabled(plugin) and not plugin_backend_missing(plugin)
        )
    return matching or candidates
