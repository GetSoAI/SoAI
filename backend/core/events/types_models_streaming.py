"""SoAI - Inference result and streaming event models [backend/core/events/types_models_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_base import Event

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "InferenceResultEvent",
    "StreamChunkEvent",
    "StreamEndEvent",
)


@dataclass(slots=True)
class InferenceResultEvent(Event):
    payload: JSONDict


@dataclass(slots=True)
class StreamChunkEvent(Event):
    chunk: bytes


@dataclass(slots=True)
class StreamEndEvent(Event):
    usage: JSONDict | None = None
