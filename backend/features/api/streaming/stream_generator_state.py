"""SoAI - Streaming generator result state [backend/features/api/streaming/stream_generator_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.payload import ErrorPublicPayload

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("StreamGeneratorState",)


@dataclass(slots=True)
class StreamGeneratorState:
    payload: JSONDict | None = None
    partial_payload: JSONDict | None = None
    done_sent: bool = False
    stream_successful: bool = True
    usage: JSONDict | None = None
    public_error: ErrorPublicPayload | None = None
