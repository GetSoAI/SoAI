"""SoAI - Streaming multipart worker-owned state [backend/features/api/routes/upload_streaming_multipart_worker_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import queue
from concurrent.futures import Future
from dataclasses import dataclass, field

from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.api.routes.upload_streaming_multipart_primitives import (
    BytesProgressEvent,
    FieldProgressEvent,
    FileStartProgressEvent,
)
from features.api.routes.upload_streaming_multipart_staging import (
    StreamingMultipartStagingSession,
)

__all__ = (
    "StreamingMultipartParts",
    "StreamingMultipartWorkerState",
    "build_worker_state",
)

_PARSER_QUEUE_DEPTH: int = 32


@dataclass(slots=True)
class StreamingMultipartParts:
    fields: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    files: list[StreamingStagedPart] = field(default_factory=list[StreamingStagedPart])
    file_bytes_done: int = 0
    file_count: int = 0


@dataclass(slots=True)
class StreamingMultipartWorkerState:
    parts: StreamingMultipartParts
    staging_session: StreamingMultipartStagingSession
    progress_queue: queue.SimpleQueue[
        BytesProgressEvent | FieldProgressEvent | FileStartProgressEvent
    ]
    chunk_queue: queue.Queue[bytes | None]
    outcome: Future[None]

    def has_failed(self) -> bool:
        if not self.outcome.done():
            return False
        return self.outcome.exception() is not None

    def raise_if_failed(self) -> None:
        if self.outcome.done():
            self.outcome.result()


def build_worker_state() -> StreamingMultipartWorkerState:
    return StreamingMultipartWorkerState(
        parts=StreamingMultipartParts(),
        staging_session=StreamingMultipartStagingSession(),
        progress_queue=queue.SimpleQueue(),
        chunk_queue=queue.Queue(maxsize=_PARSER_QUEUE_DEPTH),
        outcome=Future(),
    )
