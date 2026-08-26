"""SoAI - HTTP range responses backed by an anchored file descriptor [backend/features/api/runtime/file_descriptor_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from secrets import token_hex
from typing import override

from starlette.datastructures import MutableHeaders
from starlette.responses import FileResponse
from starlette.types import Send

from core.errors.exceptions import StateError

__all__ = ("FileDescriptorResponse",)

OPERATION_FILE_DESCRIPTOR_RESPONSE_READ = "features.api.file_descriptor_response.read"


class FileDescriptorResponse(FileResponse):
    def __init__(
        self,
        path: str,
        *,
        descriptor: int,
        stat_result: os.stat_result,
        status_code: int,
        headers: Mapping[str, str],
        media_type: str | None,
    ) -> None:
        super().__init__(
            path,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            stat_result=stat_result,
        )
        self._descriptor = descriptor
        self._size_bytes = stat_result.st_size

    @override
    async def _handle_simple(
        self,
        send: Send,
        send_header_only: bool,
        send_pathsend: bool,
    ) -> None:
        _ = send_pathsend
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        await self._send_range(
            send,
            start=0,
            end=self._size_bytes,
            send_header_only=send_header_only,
            final_chunk_closes_response=True,
        )

    @override
    async def _handle_single_range(
        self,
        send: Send,
        start: int,
        end: int,
        file_size: int,
        send_header_only: bool,
    ) -> None:
        headers = MutableHeaders(raw=list(self.raw_headers))
        headers["content-range"] = f"bytes {start}-{end - 1}/{file_size}"
        headers["content-length"] = str(end - start)
        await send(
            {
                "type": "http.response.start",
                "status": 206,
                "headers": headers.raw,
            }
        )
        await self._send_range(
            send,
            start=start,
            end=end,
            send_header_only=send_header_only,
            final_chunk_closes_response=True,
        )

    @override
    async def _handle_multiple_ranges(
        self,
        send: Send,
        ranges: list[tuple[int, int]],
        file_size: int,
        send_header_only: bool,
    ) -> None:
        boundary = token_hex(13)
        content_length, header_generator = self.generate_multipart(
            ranges,
            boundary,
            file_size,
            self.headers["content-type"],
        )
        headers = MutableHeaders(raw=list(self.raw_headers))
        headers["content-type"] = f"multipart/byteranges; boundary={boundary}"
        headers["content-length"] = str(content_length)
        await send(
            {
                "type": "http.response.start",
                "status": 206,
                "headers": headers.raw,
            }
        )
        if send_header_only:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        for start, end in ranges:
            await send(
                {
                    "type": "http.response.body",
                    "body": header_generator(start, end),
                    "more_body": True,
                }
            )
            await self._send_range(
                send,
                start=start,
                end=end,
                send_header_only=False,
                final_chunk_closes_response=False,
            )
            await send({"type": "http.response.body", "body": b"\r\n", "more_body": True})
        await send(
            {
                "type": "http.response.body",
                "body": f"--{boundary}--".encode("latin-1"),
                "more_body": False,
            }
        )

    async def _send_range(
        self,
        send: Send,
        *,
        start: int,
        end: int,
        send_header_only: bool,
        final_chunk_closes_response: bool,
    ) -> None:
        if send_header_only or start == end:
            if final_chunk_closes_response:
                await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        offset = start
        while offset < end:
            chunk = await asyncio.to_thread(
                _read_descriptor_chunk,
                self._descriptor,
                offset,
                min(self.chunk_size, end - offset),
            )
            if not chunk:
                raise StateError(
                    "Descriptor-backed response ended before its declared size.",
                    operation=OPERATION_FILE_DESCRIPTOR_RESPONSE_READ,
                )
            offset += len(chunk)
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": not final_chunk_closes_response or offset < end,
                }
            )


def _read_descriptor_chunk(descriptor: int, offset: int, size: int) -> bytes:
    os.lseek(descriptor, offset, os.SEEK_SET)
    return os.read(descriptor, size)
