"""SoAI - Model lifecycle and database event types [backend/core/events/types_models_model_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.events.types_base import Event
from core.runtime.request_context import RequestContext

__all__ = (
    "LoadFailedEvent",
    "ModelDatabaseChangeEvent",
    "ModelLoadedEvent",
    "ModelLastUsedChangedEvent",
    "ModelParametersChangedEvent",
    "ModelParametersRequireReloadEvent",
)


@dataclass(slots=True)
class ModelLoadedEvent(Event):
    context: RequestContext
    plugin_name: str
    universal_id: str


@dataclass(slots=True)
class LoadFailedEvent(Event):
    context: RequestContext
    plugin_name: str
    universal_id: str
    error: str


@dataclass(slots=True)
class ModelDatabaseChangeEvent(Event):
    added_universal_ids: list[str] = field(default_factory=list[str])
    removed_universal_ids: list[str] = field(default_factory=list[str])


@dataclass(slots=True)
class ModelLastUsedChangedEvent(Event):
    universal_id: str
    last_used_at_ms: int
    revision: int


@dataclass(slots=True)
class ModelParametersChangedEvent(Event):
    universal_id: str


@dataclass(slots=True)
class ModelParametersRequireReloadEvent(Event):
    plugin_name: str
    universal_id: str
    reason: str
