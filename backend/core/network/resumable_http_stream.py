"""SoAI - Asynchronous resumable HTTP artifact streams [backend/core/network/resumable_http_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from types import TracebackType
from typing import Self

import httpx2

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.errors.exceptions import ValidationError
from core.hardware.reservation_exceptions import preserve_primary_exception_cleanup_failure
from core.network.protocols import DownloadInterruptionProtocol
from core.network.resumable_downloads import DownloadReplayRequired, DownloadStreamState
from core.network.transfer_retry import (
    HTTP_TRANSFER_CLEANUP_EXCEPTIONS,
    HTTP_TRANSFER_EXCEPTIONS,
    wait_for_transfer_retry,
)

__all__ = ("ResumableHTTPStream",)


class ResumableHTTPStream:
    def __init__(
        self,
        opener: Callable[[Mapping[str, str], float], AbstractAsyncContextManager[httpx2.Response]],
        *,
        state: DownloadStreamState,
        interruption: DownloadInterruptionProtocol | None = None,
    ) -> None:
        self.cursor = state
        self._opener = opener
        self._interruption = interruption
        self._stack = AsyncExitStack()
        self._reader: AsyncIterator[bytes] | None = None
        self._pending: bytes | None = None

    async def __aenter__(self) -> Self:
        self.cursor.enter()
        prepared = False
        try:
            await self._connect()
            if self.cursor.replay_pending:
                self._pending = await self._next_chunk()
            prepared = True
            return self
        finally:
            if not prepared:
                self.cursor.closed = True
                await self._close_response(sys.exception())

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.cursor.closed = True
        await self._close_response(exception)

    def __aiter__(self) -> AsyncIterator[bytes]:
        self.cursor.begin_iteration()
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[bytes]:
        if self._pending:
            self._check_interruption()
            pending, self._pending = self._pending, None
            yield pending
        while not self.cursor.closed:
            chunk = await self._next_chunk()
            if chunk is None:
                return
            yield chunk

    def _check_interruption(self) -> None:
        if self._interruption is not None:
            self._interruption.raise_if_cancelled()

    async def _connect(self) -> None:
        while True:
            self._check_interruption()
            self.cursor.attempts.start()
            self._stack = AsyncExitStack()
            try:
                response = await self._stack.enter_async_context(
                    self._opener(self.cursor.request_headers(), self.cursor.timeout)
                )
                response.raise_for_status()
                self.cursor.accept(response)
                self._reader = response.aiter_raw()
                self._check_interruption()
                return
            except DownloadReplayRequired as exception:
                await self._restart(exception)
            except HTTP_TRANSFER_EXCEPTIONS as exception:
                await self._retry(exception)

    async def _next_chunk(self) -> bytes | None:
        while True:
            self._check_interruption()
            try:
                chunk = await self._read_chunk()
            except DownloadReplayRequired as exception:
                await self._restart(exception)
                await self._connect()
                continue
            except HTTP_TRANSFER_EXCEPTIONS as exception:
                await self._retry(exception)
                await self._connect()
                continue
            self._check_interruption()
            if chunk is None or chunk:
                return chunk

    async def _read_chunk(self) -> bytes | None:
        if self._reader is None:
            raise ValidationError("The artifact response is not open.")
        try:
            chunk = await anext(self._reader)
        except StopAsyncIteration:
            self.cursor.finish()
            return None
        return self.cursor.consume(chunk)

    async def _restart(self, exception: DownloadReplayRequired) -> None:
        await self._close_response(exception)
        if self.cursor.attempts.started >= self.cursor.attempts.policy.attempts:
            raise exception

    async def _retry(self, exception: BaseException) -> None:
        await self._close_response(exception)
        self._check_interruption()
        delay = self.cursor.attempts.retry_delay(exception)
        if delay is None:
            raise exception
        await wait_for_transfer_retry(delay, interruption=self._interruption)

    async def _close_response(self, primary_exception: BaseException | None) -> None:
        stack, self._stack = self._stack, AsyncExitStack()
        self._reader = None
        try:
            await cancellation_cleanup(stack.aclose())
        except HTTP_TRANSFER_CLEANUP_EXCEPTIONS as exception:
            preserve_primary_exception_cleanup_failure(
                primary_exception, exception, cleanup_action="Artifact response cleanup"
            )
            if primary_exception is not None:
                raise primary_exception from exception
