"""SoAI - Directory listing session state [backend/features/file_explorer/directory_listing_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Literal

__all__ = ("DirectoryListingRecord",)


@dataclass(slots=True)
class DirectoryListingRecord:
    listing_id: str
    user_id: int
    workspace_path: str
    virtual_path: str
    status: Literal["building", "failed", "ready", "released"]
    should_start: bool
    last_accessed_at_ms: int
    task_id: str | None = None
    snapshot_path: str | None = None
    task_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancellation_event: threading.Event = field(default_factory=threading.Event)
    io_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
