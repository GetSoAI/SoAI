"""SoAI - Manual compaction summary buffering and cancellation checks [backend/features/api/routes/webui/conversation_agent_compaction/streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.logging.protocols import LoggerProtocol
from features.api.runtime.context import ApiContext

__all__ = ("ManualCompactionDeltaStreamer",)


class ManualCompactionDeltaStreamer:
    def __init__(
        self,
        *,
        api_context: ApiContext,
        logger: LoggerProtocol,
        conv_id: str,
        user_id: int,
        turn_cancellation_id: str | None,
    ) -> None:
        _ = logger
        _ = conv_id
        _ = user_id
        self._api_context = api_context
        self._turn_cancellation_id = turn_cancellation_id

    async def raise_if_cancelled(self) -> None:
        cancellation_id = self._turn_cancellation_id
        if cancellation_id is None:
            return
        cancellation_history = self._api_context.dependencies.cancellation_history
        if cancellation_history is None:
            return
        if await cancellation_history.is_cancelled(cancellation_id):
            raise asyncio.CancelledError()

    async def on_text_delta(self, delta: str) -> None:
        normalized = str(delta or "")
        if not normalized:
            return
        await self.raise_if_cancelled()
