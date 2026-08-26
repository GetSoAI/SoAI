"""SoAI - WebSocket OpenAI runtime state types [backend/features/api/streaming/websocket_openai_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.types.json import JSONDict

if TYPE_CHECKING:
    type OpenAiAudioTranscriptionState = Literal[
        "uploading",
        "committed",
        "cancelled",
        "failed",
        "finished",
    ]

__all__ = (
    "OpenAiAudioSpeechRuntime",
    "OpenAiAudioSpeechSessionRuntime",
    "OpenAiAudioSpeechSessionSegment",
    "OpenAiAudioTranscriptionRuntime",
    "OpenAiImageGenerationRuntime",
)


@dataclass(slots=True)
class OpenAiAudioTranscriptionRuntime:
    run_id: str
    user_id: int
    started_at_ms: int
    original_filename: str
    temp_path: str
    fields: dict[str, tuple[str, ...]]
    received_bytes: int
    next_sequence: int
    active_task_id: str | None
    detach_event: asyncio.Event | None
    runner_task: asyncio.Task[None] | None
    lock: asyncio.Lock
    state: OpenAiAudioTranscriptionState
    sealed_bytes: int


@dataclass(slots=True)
class OpenAiAudioSpeechRuntime:
    run_id: str
    user_id: int
    started_at_ms: int
    task_id: str
    detach_event: asyncio.Event | None
    runner_task: asyncio.Task[None] | None


@dataclass(frozen=True, slots=True)
class OpenAiAudioSpeechSessionSegment:
    segment_sequence: int
    input: str


@dataclass(slots=True)
class OpenAiAudioSpeechSessionRuntime:
    run_id: str
    user_id: int
    started_at_ms: int
    payload: JSONDict
    media_type: str
    queue: asyncio.Queue[OpenAiAudioSpeechSessionSegment]
    lock: asyncio.Lock
    state_event: asyncio.Event
    detach_event: asyncio.Event
    runner_task: asyncio.Task[None] | None
    active_task_id: str | None
    admitting_task: bool
    sealed: bool
    next_segment_sequence: int
    terminal_emitted: bool


@dataclass(slots=True)
class OpenAiImageGenerationRuntime:
    run_id: str
    user_id: int
    started_at_ms: int
    active_task_id: str | None
    detach_event: asyncio.Event | None
    runner_task: asyncio.Task[None] | None
