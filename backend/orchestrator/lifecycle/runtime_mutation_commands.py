"""SoAI - Runtime mutation command models [backend/orchestrator/lifecycle/runtime_mutation_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.events.types_base import Event

__all__ = ("RuntimeMutationStopRequest",)


@dataclass(frozen=True, slots=True)
class RuntimeMutationStopRequest:
    plugin_name: str
    reason: str = "Plugin stop requested"
    reply_channel: asyncio.Queue[Event] | None = None
    publish_state_changes: bool = True
    wait_for_state_changes: bool = True
    force: bool = False
    stop_timeout_sec: float | None = None
    lock_acquire_timeout_sec: float | None = None
