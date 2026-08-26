"""SoAI - File-related events and commands [backend/core/events/types_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.events.types_base import ReplyableUserCommand
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "FileContentQuery",
    "FileDeleteCommand",
    "FileRetrieveQuery",
    "FileStatus",
    "FileUploadCommand",
)


class FileStatus(Enum):
    UPLOADED = "uploaded"
    PROCESSED = "processed"
    ERROR = "error"


@dataclass(slots=True)
class FileUploadCommand(ReplyableUserCommand):
    context: RequestContext
    temp_file_path: str
    original_filename: str
    purpose: str
    content_sha256: str
    user_id: int | None = None
    api_key_id: str | None = None


@dataclass(slots=True)
class FileRetrieveQuery(ReplyableUserCommand):
    context: RequestContext
    file_id: str
    user_id: int | None = None
    api_key_id: str | None = None


@dataclass(slots=True)
class FileDeleteCommand(ReplyableUserCommand):
    context: RequestContext
    file_id: str
    user_id: int | None = None
    api_key_id: str | None = None


@dataclass(slots=True)
class FileContentQuery(ReplyableUserCommand):
    context: RequestContext
    payload: JSONDict
    user_id: int | None = None
    api_key_id: str | None = None
