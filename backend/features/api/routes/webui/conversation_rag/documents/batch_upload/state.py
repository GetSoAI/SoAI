"""SoAI - WebUI RAG batch upload state types [backend/features/api/routes/webui/conversation_rag/documents/batch_upload/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("RagBatchFailedPart", "RagBatchKnowledgeState", "RagBatchUploadMultipartState")


@dataclass(slots=True)
class RagBatchUploadMultipartState:
    bytes_done: int = 0
    stream_bytes_done: int = 0
    last_filename: str = "batch"
    file_counter: int = 0
    processed_file_count: int = 0
    queued_file_count: int = 0

    def report_bytes(self, bytes_done: int) -> None:
        self.bytes_done = int(bytes_done)

    def report_stream_bytes(self, bytes_done: int) -> None:
        self.stream_bytes_done = int(bytes_done)

    def report_file_start(self, filename: str) -> None:
        self.last_filename = filename
        self.file_counter += 1


@dataclass(frozen=True, slots=True)
class RagBatchFailedPart:
    item_index: int
    filename: str
    file_type: str
    file_size_bytes: int | None
    rag_status: str
    error_message: str


@dataclass(slots=True)
class RagBatchKnowledgeState:
    knowledge_attachment_id: str | None = None
    latest_summary: JSONDict | None = None
