"""SoAI - Streaming multipart parser thread lifecycle and cleanup [backend/features/api/routes/upload_streaming_multipart_threading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from python_multipart.exceptions import FormParserError

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.threading_async import join_thread
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    StateError,
    ValidationError,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from features.api.routes import upload_streaming_multipart_processing
from features.api.routes.upload_streaming_multipart_models import StreamingMultipartSpec
from features.api.routes.upload_streaming_multipart_permit import (
    MultipartParserSemaphorePermit,
)
from features.api.routes.upload_streaming_multipart_primitives import drain_and_signal_queue
from features.api.routes.upload_streaming_multipart_worker_state import (
    StreamingMultipartWorkerState,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from features.api.routes.internal_protocols import StreamingMultipartWriteController

__all__ = (
    "cleanup_state",
    "join_parser_thread_or_raise",
    "multipart_parser_worker",
    "start_parser_thread",
)

OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_CLEANUP_STAGING_SESSION = (
    "api_routes.parse_streaming_multipart.cleanup_staging_session"
)
OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_CLEANUP_THREAD_JOIN = (
    "api_routes.parse_streaming_multipart.cleanup_thread_join"
)
OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PARSER_WORKER = (
    "api_routes.parse_streaming_multipart.parser_worker"
)
OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_FINISH_WRITE_CONTROLLER = (
    "api_routes.parse_streaming_multipart.finish_write_controller"
)

LOGGER_NAME = "SoAI.features.api.upload_streaming_multipart_threading"


def multipart_parser_worker(
    spec: StreamingMultipartSpec,
    token: CancellationTokenProtocol,
    logger_name: str,
    content_type: str,
    boundary: bytes,
    state: StreamingMultipartWorkerState,
    write_controller: StreamingMultipartWriteController,
    permit: MultipartParserSemaphorePermit,
) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.debug("Starting multipart parser worker: %s", logger_name)
    worker_completed = False
    try:
        try:
            upload_streaming_multipart_processing.process_multipart_stream(
                spec=spec,
                token=token,
                logger=logger,
                content_type=content_type,
                boundary=boundary,
                state=state,
                write_controller=write_controller,
            )
        except (
            ValidationError,
            InsufficientDiskSpaceError,
            PayloadTooLargeError,
            StateError,
            TaskCancelledError,
            FormParserError,
        ) as exception:
            state.outcome.set_exception(exception)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PARSER_WORKER,
            )
            log_exception(
                logger,
                coerced,
                message="Unexpected error in multipart parser thread",
                operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PARSER_WORKER,
            )
            state.outcome.set_exception(coerced)
        except (SystemExit, KeyboardInterrupt, GeneratorExit) as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PARSER_WORKER,
            )
            log_exception(
                logger,
                coerced,
                message="Multipart parser thread terminated unexpectedly",
                operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PARSER_WORKER,
            )
            state.outcome.set_exception(coerced)
        else:
            worker_completed = True
            state.outcome.set_result(None)
        finally:
            if not worker_completed:
                drain_and_signal_queue(state.chunk_queue)
    finally:
        if not state.outcome.done():
            state.outcome.set_exception(
                StateError(
                    "Multipart parser thread terminated without recording an outcome.",
                    operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_PARSER_WORKER,
                )
            )
        try:
            try:
                state.staging_session.cleanup_if_requested()
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_CLEANUP_STAGING_SESSION,
                )
                log_handled_exception(
                    logger,
                    coerced,
                    message="Multipart parser deferred staging cleanup failed.",
                    operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_CLEANUP_STAGING_SESSION,
                    level="debug",
                )
        finally:
            try:
                try:
                    write_controller.parser_finished()
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    coerced = coerce_to_soai_error(
                        exception,
                        operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_FINISH_WRITE_CONTROLLER,
                    )
                    log_handled_exception(
                        logger,
                        coerced,
                        message="Multipart parser write-controller finalization failed.",
                        operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_FINISH_WRITE_CONTROLLER,
                        level="error",
                    )
            finally:
                permit.release_from_worker(logger=logger)


def start_parser_thread(
    *,
    state: StreamingMultipartWorkerState,
    spec: StreamingMultipartSpec,
    token: CancellationTokenProtocol,
    logger_name: str,
    content_type: str,
    boundary: bytes,
    write_controller: StreamingMultipartWriteController,
    permit: MultipartParserSemaphorePermit,
) -> threading.Thread:
    parser_thread = threading.Thread(
        target=multipart_parser_worker,
        args=(
            spec,
            token,
            logger_name,
            content_type,
            boundary,
            state,
            write_controller,
            permit,
        ),
        name="soai-multipart-parser",
        daemon=True,
    )
    write_controller.parser_started()
    permit.transfer_to_worker()
    try:
        parser_thread.start()
    except RuntimeError:
        permit.release_after_start_failure()
        write_controller.parser_finished()
        raise
    return parser_thread


async def join_parser_thread_or_raise(
    parser_thread: threading.Thread,
    *,
    state: StreamingMultipartWorkerState,
    token: CancellationTokenProtocol,
) -> None:
    if await join_thread(parser_thread, timeout=INTERACTIVE_TIMEOUT_SEC):
        return
    token.cancel("Multipart parser thread did not exit within timeout.")
    drain_and_signal_queue(state.chunk_queue)
    raise StateError(
        "Multipart parser thread did not exit within timeout.",
        operation="api_routes.parse_streaming_multipart.thread_join",
    )


async def cleanup_state(
    *,
    state: StreamingMultipartWorkerState,
    parser_thread: threading.Thread,
    token: CancellationTokenProtocol,
    logger: TraceLogger,
    should_cleanup: bool,
) -> None:
    if should_cleanup:
        state.staging_session.request_cleanup()
    drain_and_signal_queue(state.chunk_queue)
    if parser_thread.is_alive():
        token.cancel("Multipart parser cleanup requested.")
        await join_thread(parser_thread, timeout=INTERACTIVE_TIMEOUT_SEC)
    if parser_thread.is_alive():
        log_exception(
            logger,
            StateError(
                "Multipart parser thread did not exit within timeout during cleanup.",
                operation="api_routes.parse_streaming_multipart.cleanup_thread_join",
                details={"timeout_sec": INTERACTIVE_TIMEOUT_SEC},
            ),
            message="Multipart parser-owned resources remain until its worker exits.",
            operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_CLEANUP_THREAD_JOIN,
        )
        return
    if should_cleanup:
        state.staging_session.cleanup()
