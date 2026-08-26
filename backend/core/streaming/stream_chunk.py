"""SoAI - Canonical streaming chunk contract [backend/core/streaming/stream_chunk.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

__all__: tuple[()] = ()

if TYPE_CHECKING:
    type StreamChunk = bytes | bytearray | memoryview | str
