"""SoAI - Assistant timeline protocols [backend/features/assistant_timeline/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import Protocol

__all__ = ("AssistantTimelineTickerOwner",)


class AssistantTimelineTickerOwner(Protocol):
    wait_for_user_tick_task: asyncio.Task[None] | None
    processing_tick_task: asyncio.Task[None] | None
    status_preview_tick_task: asyncio.Task[None] | None
