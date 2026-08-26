"""SoAI - Shared streaming runtime types [backend/features/agent/runtime/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from core.events.types_base import Event
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.tasks.task import Task
from core.types.json import JSONDict

__all__ = ("StreamingRunnerCallbackBases",)


@dataclass(frozen=True, slots=True)
class StreamingRunnerCallbackBases:
    create_additional_task: Callable[
        [
            JSONDict,
            RequestContext,
            str,
            Callable[[bytes], Awaitable[None] | None],
        ],
        Awaitable[tuple[Task, asyncio.Queue[Event]]],
    ]
    create_stream_generator: Callable[
        [
            asyncio.Queue[Event],
            RequestContext,
            Task,
            StreamGeneratorStateProtocol,
            OpenAIStreamTranscript,
        ],
        AsyncIterator[bytes],
    ]
