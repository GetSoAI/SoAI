"""SoAI - Binary orchestrator stream delivery and replay handling [backend/orchestrator/execution/streaming_binary_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.openai.wav_metadata import resolve_wav_duration_seconds
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from orchestrator.execution.binary_dedup_replay import BinaryReplayRecorder
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.result_processing_error import ResultProcessingError
from orchestrator.execution.stream_delivery import deliver_stream_chunk
from orchestrator.execution.stream_iteration import (
    StreamIterationRequest,
    build_stream_iterator,
)

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "BinaryStreamingResult",
    "handle_streaming_binary",
)

LOGGER_NAME = "SoAI.orchestrator.execution.streaming_binary_result"
OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY = (
    "orchestrator.handle_streaming_result.binary"
)
OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY_FINALIZE = (
    "orchestrator.handle_streaming_result.binary.finalize"
)
_BINARY_STREAM_HEADER_LIMIT_BYTES = 4096


def _detect_binary_progress(chunk: bytes) -> bool:
    return bool(chunk)


@dataclass(frozen=True, slots=True)
class BinaryStreamingResult:
    replay_temp_path: str | None
    output_bytes: int
    output_duration_seconds: float | None


async def handle_streaming_binary(
    *,
    queue: OrchestratorQueueProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    task: Task,
    result: AsyncIterable[StreamChunk],
    tracking_id: str,
    streaming_chunk_delivery_timeout: float,
    first_chunk_timeout: float,
    streaming_idle_timeout: float,
    temp_directory: str | None,
    dedup_hash: str | None,
) -> BinaryStreamingResult:
    logger = get_logger(LOGGER_NAME)
    replay_recorder = await _create_binary_replay_recorder(
        dedup_hash=dedup_hash,
        temp_directory=temp_directory,
        logger=logger,
    )
    output_bytes = 0
    header_sample = bytearray()
    stream_completed = False
    try:
        stream_iterator = build_stream_iterator(
            StreamIterationRequest(
                streaming_idle_timeout=streaming_idle_timeout,
                first_chunk_timeout=first_chunk_timeout,
                tracking_id=tracking_id,
                result=result,
                task=task,
                active_inferences=active_inferences,
                queue=queue,
                detect_progress=_detect_binary_progress,
            ),
        )
        async for chunk_bytes in stream_iterator:
            output_bytes += len(chunk_bytes)
            if len(header_sample) < _BINARY_STREAM_HEADER_LIMIT_BYTES:
                remaining = _BINARY_STREAM_HEADER_LIMIT_BYTES - len(header_sample)
                header_sample.extend(chunk_bytes[:remaining])
            await deliver_stream_chunk(
                task=task,
                chunk_bytes=chunk_bytes,
                streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
                operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
                logger=logger,
            )
            if replay_recorder is not None:
                await replay_recorder.write_chunk(
                    chunk_bytes,
                    timeout_sec=streaming_chunk_delivery_timeout,
                )
        stream_completed = True
    except TimeoutError as exception:
        raise _coerce_binary_replay_io_error(
            exception,
            logger=logger,
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
            message="Streaming binary replay handling timed out.",
        ) from exception
    except OSError as exception:
        raise _coerce_binary_replay_io_error(
            exception,
            logger=logger,
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
            message="Streaming binary replay handling failed.",
        ) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(
            exception,
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
        )
        log_exception(
            logger,
            coerced_exception,
            message="Streaming binary replay handling failed.",
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
        )
        raise coerced_exception from exception
    finally:
        if not stream_completed:
            await _discard_binary_replay_recorder(replay_recorder, logger)
    if replay_recorder is None:
        return BinaryStreamingResult(
            replay_temp_path=None,
            output_bytes=output_bytes,
            output_duration_seconds=resolve_wav_duration_seconds(header_sample),
        )
    replay_temp_path = await _finalize_binary_replay(
        replay_recorder=replay_recorder,
        streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
        logger=logger,
    )
    return BinaryStreamingResult(
        replay_temp_path=replay_temp_path,
        output_bytes=output_bytes,
        output_duration_seconds=resolve_wav_duration_seconds(header_sample),
    )


async def _create_binary_replay_recorder(
    *,
    dedup_hash: str | None,
    temp_directory: str | None,
    logger: TraceLogger,
) -> BinaryReplayRecorder | None:
    if not dedup_hash:
        return None
    if temp_directory is None:
        raise StateError("Missing temp directory for deduplicated binary replay.")
    try:
        return await BinaryReplayRecorder.create(temp_directory)
    except OSError as exception:
        raise _coerce_binary_replay_io_error(
            exception,
            logger=logger,
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
            message="Streaming binary replay creation failed.",
        ) from exception


async def _finalize_binary_replay(
    *,
    replay_recorder: BinaryReplayRecorder,
    streaming_chunk_delivery_timeout: float,
    logger: TraceLogger,
) -> str:
    finalized = False
    try:
        replay_temp_path = await replay_recorder.finalize(
            timeout_sec=streaming_chunk_delivery_timeout,
        )
        finalized = True
        return replay_temp_path
    except TimeoutError as exception:
        raise _coerce_binary_replay_io_error(
            exception,
            logger=logger,
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY_FINALIZE,
            message="Streaming binary replay finalization timed out.",
        ) from exception
    except OSError as exception:
        raise _coerce_binary_replay_io_error(
            exception,
            logger=logger,
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY_FINALIZE,
            message="Streaming binary replay finalization failed.",
        ) from exception
    finally:
        if not finalized:
            await _discard_binary_replay_recorder(replay_recorder, logger)


async def _discard_binary_replay_recorder(
    replay_recorder: BinaryReplayRecorder | None,
    logger: TraceLogger,
) -> None:
    if replay_recorder is None:
        return
    try:
        await replay_recorder.discard()
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to discard binary replay temp file.",
            operation=OPERATION_ORCHESTRATOR_HANDLE_STREAMING_RESULT_BINARY,
            level="warning",
        )


def _coerce_binary_replay_io_error(
    exception: OSError | TimeoutError,
    *,
    logger: TraceLogger,
    operation: str,
    message: str,
) -> ResultProcessingError:
    result_exception = ResultProcessingError(
        "Internal binary streaming replay IO failed.",
        operation=operation,
        details={"error": str(exception)},
        cause=exception,
    )
    log_exception(
        logger,
        result_exception,
        message=message,
        operation=operation,
    )
    return result_exception
