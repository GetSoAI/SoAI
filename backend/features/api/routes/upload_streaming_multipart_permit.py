"""SoAI - Multipart parser concurrency permit ownership across the parser thread boundary [backend/features/api/routes/upload_streaming_multipart_permit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.logging.protocols import TraceLogger

__all__ = ("MultipartParserSemaphorePermit",)

OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_RELEASE_PARSER_PERMIT = (
    "api_routes.parse_streaming_multipart.release_parser_permit"
)


class MultipartParserSemaphorePermit:
    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self._loop = loop
        self._semaphore = semaphore
        self._lock = threading.Lock()
        self._worker_owns_permit = False
        self._released = False

    def transfer_to_worker(self) -> None:
        with self._lock:
            if self._worker_owns_permit or self._released:
                raise StateError("Multipart parser semaphore permit cannot be transferred.")
            self._worker_owns_permit = True

    def release_after_start_failure(self) -> None:
        with self._lock:
            if not self._worker_owns_permit or self._released:
                raise StateError("Multipart parser semaphore permit is not worker-owned.")
            self._worker_owns_permit = False
            self._released = True
        self._semaphore.release()

    def release_without_worker(self) -> None:
        with self._lock:
            if self._released:
                return
            if self._worker_owns_permit:
                raise StateError("Multipart parser semaphore permit cannot be released by request.")
            self._released = True
        self._semaphore.release()

    def release_from_worker(self, *, logger: TraceLogger) -> None:
        with self._lock:
            if not self._worker_owns_permit or self._released:
                raise StateError("Multipart parser semaphore permit is not worker-owned.")
            self._worker_owns_permit = False
            self._released = True
        try:
            self._loop.call_soon_threadsafe(self._semaphore.release)
        except RuntimeError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Multipart parser event loop closed before permit release.",
                operation=OPERATION_API_ROUTES_PARSE_STREAMING_MULTIPART_RELEASE_PARSER_PERMIT,
                level="debug",
            )
