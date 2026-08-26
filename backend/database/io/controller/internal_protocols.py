"""SoAI - Database I/O controller internal protocols [backend/database/io/controller/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from queue import Queue
from typing import Protocol

from database.io.internal_protocols import DatabaseWriteJobProtocol, ShutdownSentinel
from database.io.operation_status_tracker import OperationStatusTracker

__all__ = ("DatabaseIOControllerRecoveryStateProtocol",)


class DatabaseIOControllerRecoveryStateProtocol(Protocol):
    queue: Queue[DatabaseWriteJobProtocol | type[ShutdownSentinel]]
    thread: threading.Thread | None
    shutdown_event: threading.Event
    runtime_start_event: threading.Event
    runtime_ready_event: threading.Event
    writer_session_active: threading.Event
    bound_loop: asyncio.AbstractEventLoop | None
    connect_timeout: float
    init_timeout: float
    shutdown_timeout: float
    init_error: BaseException | None
    operation_status_tracker: OperationStatusTracker

    def interrupt_active_connection(self) -> bool: ...
