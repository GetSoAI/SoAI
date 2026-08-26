"""SoAI - NDJSON framing for IPC streams [backend/core/ipc/ndjson.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.ipc.message_encoding import encode_ipc_message_bytes
from core.serialization.json_parsing import parse_json_value
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "IpcStreamClosedError",
    "NdjsonCodec",
)

IPC_DEFAULT_MAX_LINE_BYTES = 256 * MIB_BYTES


class IpcStreamClosedError(ValidationError): ...


class NdjsonCodec:
    def __init__(self, *, max_line_bytes: int = IPC_DEFAULT_MAX_LINE_BYTES) -> None:
        max_value = int(max_line_bytes)
        if max_value < 1024:
            raise ValidationError("max_line_bytes must be at least 1024.")
        self._max_line_bytes = max_value

    @staticmethod
    def default_max_line_bytes() -> int:
        return IPC_DEFAULT_MAX_LINE_BYTES

    @property
    def stream_limit_bytes(self) -> int:
        return self._max_line_bytes + 1

    @property
    def max_line_bytes(self) -> int:
        return self._max_line_bytes

    async def read_message(
        self,
        reader: asyncio.StreamReader,
        *,
        timeout_sec: float | None,
    ) -> JSONDict:
        try:
            line = await self._readline(reader, timeout_sec=timeout_sec)
        except ValueError as exception:
            raise ValidationError("IPC message exceeds maximum size.") from exception
        if not line:
            raise IpcStreamClosedError("IPC stream closed.")
        if len(line) > self._max_line_bytes:
            raise ValidationError("IPC message exceeds maximum size.")
        try:
            decoded = line.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError as exception:
            raise ValidationError("IPC message is not valid UTF-8.") from exception
        if not decoded:
            raise ValidationError("IPC message is empty.")
        try:
            parsed = parse_json_value(decoded)
        except ValidationError as exception:
            raise ValidationError("IPC message is not valid JSON.") from exception
        if not isinstance(parsed, dict):
            raise ValidationError("IPC message must be a JSON object.")
        return parsed

    async def _readline(
        self,
        reader: asyncio.StreamReader,
        *,
        timeout_sec: float | None,
    ) -> bytes:
        if timeout_sec is None:
            return await self._readline_without_deadline(reader)
        timeout_value = max(0.1, float(timeout_sec))
        return await asyncio.wait_for(reader.readline(), timeout=timeout_value)

    async def _readline_without_deadline(self, reader: asyncio.StreamReader) -> bytes:
        while True:
            try:
                return await asyncio.wait_for(reader.readline(), timeout=LONG_IDLE_TIMEOUT_SEC)
            except TimeoutError:
                continue

    async def write_message(
        self,
        writer: asyncio.StreamWriter,
        message: JSONDict,
        *,
        timeout_sec: float,
    ) -> None:
        data = encode_ipc_message_bytes(message, max_bytes=self._max_line_bytes)
        try:
            writer.write(data)
            timeout_value = max(0.1, float(timeout_sec))
            await asyncio.wait_for(writer.drain(), timeout=timeout_value)
        except ConnectionError as exception:
            raise IpcStreamClosedError("IPC stream closed.") from exception
