"""SoAI - Synchronous resumable HTTP artifact streams [backend/core/network/resumable_http_stream_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, ExitStack
from types import TracebackType
from typing import Self

import httpx2

from core.errors.exceptions import ValidationError
from core.hardware.reservation_exceptions import preserve_primary_exception_cleanup_failure
from core.network.resumable_downloads import DownloadReplayRequired, DownloadStreamState
from core.network.transfer_retry import (
    HTTP_TRANSFER_CLEANUP_EXCEPTIONS,
    HTTP_TRANSFER_EXCEPTIONS,
)
from core.timing.sleep import sleep_seconds
from core.validation.strict_numbers import require_positive_int_strict

__all__ = ("ResumableHTTPStreamSync",)


class ResumableHTTPStreamSync:
    def __init__(
        self,
        opener: Callable[[Mapping[str, str], float], AbstractContextManager[httpx2.Response]],
        *,
        state: DownloadStreamState,
        chunk_size: int = 65536,
    ) -> None:
        require_positive_int_strict(chunk_size, error_message="Chunk size must be positive.")
        self.cursor = state
        self._opener = opener
        self._chunk_size = chunk_size
        self._stack = ExitStack()
        self._reader: Iterator[bytes] | None = None
        self._pending: bytes | None = None

    def __enter__(self) -> Self:
        self.cursor.enter()
        prepared = False
        try:
            self._connect()
            if self.cursor.replay_pending:
                self._pending = self._next_chunk()
            prepared = True
            return self
        finally:
            if not prepared:
                self.cursor.closed = True
                self._close_response(sys.exception())

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.cursor.closed = True
        self._close_response(exception)

    def __iter__(self) -> Iterator[bytes]:
        self.cursor.begin_iteration()
        return self._iterate()

    def _iterate(self) -> Iterator[bytes]:
        if self._pending:
            pending, self._pending = self._pending, None
            yield pending
        while not self.cursor.closed:
            chunk = self._next_chunk()
            if chunk is None:
                return
            yield chunk

    def _connect(self) -> None:
        while True:
            self.cursor.attempts.start()
            self._stack = ExitStack()
            try:
                response = self._stack.enter_context(
                    self._opener(self.cursor.request_headers(), self.cursor.timeout)
                )
                response.raise_for_status()
                self.cursor.accept(response)
                self._reader = response.iter_raw(chunk_size=self._chunk_size)
                return
            except DownloadReplayRequired as exception:
                self._restart(exception)
            except HTTP_TRANSFER_EXCEPTIONS as exception:
                self._retry(exception)

    def _next_chunk(self) -> bytes | None:
        while True:
            try:
                chunk = self._read_chunk()
            except DownloadReplayRequired as exception:
                self._restart(exception)
                self._connect()
                continue
            except HTTP_TRANSFER_EXCEPTIONS as exception:
                self._retry(exception)
                self._connect()
                continue
            if chunk is None or chunk:
                return chunk

    def _read_chunk(self) -> bytes | None:
        if self._reader is None:
            raise ValidationError("The artifact response is not open.")
        try:
            chunk = next(self._reader)
        except StopIteration:
            self.cursor.finish()
            return None
        return self.cursor.consume(chunk)

    def _restart(self, exception: DownloadReplayRequired) -> None:
        self._close_response(exception)
        if self.cursor.attempts.started >= self.cursor.attempts.policy.attempts:
            raise exception

    def _retry(self, exception: BaseException) -> None:
        self._close_response(exception)
        delay = self.cursor.attempts.retry_delay(exception)
        if delay is None:
            raise exception
        sleep_seconds(delay)

    def _close_response(self, primary_exception: BaseException | None) -> None:
        stack, self._stack = self._stack, ExitStack()
        self._reader = None
        try:
            stack.close()
        except HTTP_TRANSFER_CLEANUP_EXCEPTIONS as exception:
            preserve_primary_exception_cleanup_failure(
                primary_exception, exception, cleanup_action="Artifact response cleanup"
            )
            if primary_exception is not None:
                raise primary_exception from exception
