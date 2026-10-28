"""SoAI - Speech-to-text catalog snapshot values [backend/core/media/speech_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "SpeechCatalogSnapshot",
    "SpeechModelEntry",
    "SpeechPluginEntry",
)


@dataclass(frozen=True, slots=True)
class SpeechPluginEntry:
    plugin_name: str
    display_name: str
    state: str
    local_models: bool
    transcription: bool
    translation: bool
    supports_backend_installation: bool
    supports_model_download: bool
    decoding_parameters: JSONDict = field(default_factory=dict[str, JSONValue])


@dataclass(frozen=True, slots=True)
class SpeechModelEntry:
    universal_id: str
    plugin_name: str
    model_info: JSONDict


@dataclass(frozen=True, slots=True)
class SpeechCatalogSnapshot:
    plugins: tuple[SpeechPluginEntry, ...]
    models: tuple[SpeechModelEntry, ...]
