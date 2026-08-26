"""SoAI - Assistant timeline ticker shutdown helpers [backend/features/assistant_timeline/assistant_timeline_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.task_finalization import cancel_and_await_task
from features.assistant_timeline.internal_protocols import AssistantTimelineTickerOwner

__all__ = ("stop_timeline_session_tickers",)


async def stop_timeline_session_tickers(session: AssistantTimelineTickerOwner) -> None:
    wait_for_user_tick_task = session.wait_for_user_tick_task
    session.wait_for_user_tick_task = None
    await cancel_and_await_task(wait_for_user_tick_task)
    processing_tick_task = session.processing_tick_task
    session.processing_tick_task = None
    await cancel_and_await_task(processing_tick_task)
    status_preview_tick_task = session.status_preview_tick_task
    session.status_preview_tick_task = None
    await cancel_and_await_task(status_preview_tick_task)
