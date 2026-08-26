"""SoAI - File explorer event type definitions [backend/core/events/types_file_explorer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.events.types_base import Event, EventDelivery

__all__ = (
    "FileExplorerOperation",
    "FileSystemChangedEvent",
)


class FileExplorerOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"
    MKDIR = "mkdir"


@dataclass(slots=True)
class FileSystemChangedEvent(Event):
    operation: FileExplorerOperation
    virtual_path: str
    is_directory: bool
    destination_virtual_path: str | None = None
    workspace_root_path: str = ""
    delivery: EventDelivery = EventDelivery.DROPPABLE
