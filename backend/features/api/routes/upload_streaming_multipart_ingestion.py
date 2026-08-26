"""SoAI - Streaming multipart request-body ingestion to parser thread [backend/features/api/routes/upload_streaming_multipart_ingestion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.protocols import TraceLogger
from features.api.routes.internal_protocols import (
    MultipartBytesReporter,
    MultipartFieldReporter,
    MultipartFileStartReporter,
)
from features.api.routes.upload_streaming_multipart_primitives import (
    drain_and_signal_queue,
)
from features.api.routes.upload_streaming_multipart_processing import (
    drain_progress_callbacks,
)
from features.api.routes.upload_streaming_multipart_queueing import enqueue_parser_chunk
from features.api.routes.upload_streaming_multipart_worker_state import (
    StreamingMultipartWorkerState,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "drain_progress",
    "enqueue_chunk_or_fail",
    "finalize_parser_input",
    "ingest_request_stream",
    "note_stream_bytes_done",
)


def drain_progress(
    *,
    state: StreamingMultipartWorkerState,
    report_bytes: MultipartBytesReporter,
    report_field: MultipartFieldReporter | None,
    report_file_start: MultipartFileStartReporter | None,
    token: CancellationTokenProtocol,
    logger: TraceLogger,
) -> Exception | None:
    return drain_progress_callbacks(
        progress_queue=state.progress_queue,
        report_bytes=report_bytes,
        report_field=report_field,
        report_file_start=report_file_start,
        token=token,
        logger=logger,
        chunk_queue=state.chunk_queue,
    )


def note_stream_bytes_done(
    *,
    stream_bytes_done: int,
    chunk: bytes,
    report_stream_bytes: MultipartBytesReporter | None,
) -> int:
    next_stream_bytes_done = stream_bytes_done + len(chunk)
    if report_stream_bytes is not None:
        report_stream_bytes(next_stream_bytes_done)
    return next_stream_bytes_done


async def enqueue_chunk_or_fail(
    *,
    state: StreamingMultipartWorkerState,
    item: bytes | None,
    token: CancellationTokenProtocol,
    stall_message: str,
) -> None:
    was_enqueued = await enqueue_parser_chunk(
        state,
        item=item,
        token=token,
    )
    if was_enqueued:
        return
    token.cancel(stall_message)
    drain_and_signal_queue(state.chunk_queue)
    raise ValidationError("Invalid multipart payload.")


async def ingest_request_stream(
    request: Request,
    *,
    state: StreamingMultipartWorkerState,
    token: CancellationTokenProtocol,
    report_bytes: MultipartBytesReporter,
    report_field: MultipartFieldReporter | None,
    report_file_start: MultipartFileStartReporter | None,
    report_stream_bytes: MultipartBytesReporter | None,
    logger: TraceLogger,
) -> Exception | None:
    stream_bytes_done = 0
    async for chunk in request.stream():
        token.raise_if_cancelled()
        callback_error = drain_progress(
            state=state,
            report_bytes=report_bytes,
            report_field=report_field,
            report_file_start=report_file_start,
            token=token,
            logger=logger,
        )
        if callback_error is not None:
            return callback_error
        if not chunk:
            continue
        stream_bytes_done = note_stream_bytes_done(
            stream_bytes_done=stream_bytes_done,
            chunk=chunk,
            report_stream_bytes=report_stream_bytes,
        )
        await enqueue_chunk_or_fail(
            state=state,
            item=chunk,
            token=token,
            stall_message="Multipart parser stalled while reading request body.",
        )
        callback_error = drain_progress(
            state=state,
            report_bytes=report_bytes,
            report_field=report_field,
            report_file_start=report_file_start,
            token=token,
            logger=logger,
        )
        if state.has_failed() or callback_error is not None:
            return callback_error
        token.raise_if_cancelled()
    return None


async def finalize_parser_input(
    *,
    state: StreamingMultipartWorkerState,
    token: CancellationTokenProtocol,
    callback_error: Exception | None,
) -> None:
    if state.has_failed() or callback_error is not None:
        return
    await enqueue_chunk_or_fail(
        state=state,
        item=None,
        token=token,
        stall_message="Multipart parser stalled while finalizing request body.",
    )
