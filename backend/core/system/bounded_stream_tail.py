"""SoAI - Bounded subprocess diagnostic stream capture [backend/core/system/bounded_stream_tail.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from core.errors.exceptions import ValidationError
from core.timing.constants import BACKGROUND_TIMEOUT_SEC

__all__ = ("BoundedStreamTail",)


@dataclass(slots=True)
class BoundedStreamTail:
    maximum_bytes: int
    received_bytes: int = 0
    content: bytearray = field(default_factory=bytearray)

    def __post_init__(self) -> None:
        if self.maximum_bytes < 1:
            raise ValidationError("Diagnostic stream capacity must be positive.")

    async def drain(self, reader: asyncio.StreamReader) -> None:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    reader.read(min(self.maximum_bytes, 16384)), timeout=BACKGROUND_TIMEOUT_SEC
                )
            except TimeoutError:
                continue
            if not chunk:
                return
            self.received_bytes += len(chunk)
            self.content.extend(chunk)
            del self.content[: max(0, len(self.content) - self.maximum_bytes)]

    def diagnostic(self) -> str:
        truncated = max(0, self.received_bytes - len(self.content))
        text = self.content.decode("utf-8", errors="replace")
        return f"{text}\n[truncated_bytes={truncated}]" if truncated else text
