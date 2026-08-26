"""SoAI - Thread-safe staged multipart file ownership and cleanup [backend/features/api/routes/upload_streaming_multipart_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import threading

from core.errors.exceptions import StateError
from features.api.routes.internal_protocols import MultipartStagingWriter
from features.api.routes.upload_streaming_multipart_cleanup import (
    cleanup_staged_multipart_upload,
)

__all__ = ("StreamingMultipartStagingSession",)


class StreamingMultipartStagingSession:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._cleanup_requested = False
        self._cleanup_active = False
        self._cleanup_completed = False
        self._opened_paths: list[str] = []
        self._opened_writers: list[MultipartStagingWriter] = []

    def register_path(self, path: str) -> None:
        with self._condition:
            while self._cleanup_active:
                self._condition.wait()
            self._opened_paths.append(path)
            self._cleanup_completed = False
            if self._cleanup_requested:
                raise StateError("Multipart staging session is closed.")

    def register_writer(self, writer: MultipartStagingWriter) -> None:
        with self._condition:
            while self._cleanup_active:
                self._condition.wait()
            self._opened_writers.append(writer)
            self._cleanup_completed = False
            if self._cleanup_requested:
                raise StateError("Multipart staging session is closed.")

    def cleanup(self) -> None:
        self.request_cleanup()
        self.cleanup_if_requested()

    def request_cleanup(self) -> None:
        with self._condition:
            self._cleanup_requested = True

    def cleanup_if_requested(self) -> None:
        with self._condition:
            while self._cleanup_active:
                self._condition.wait()
            if not self._cleanup_requested or self._cleanup_completed:
                return
            self._cleanup_active = True
            writers = list(self._opened_writers)
            paths = list(self._opened_paths)
        result = cleanup_staged_multipart_upload(
            opened_writers=writers,
            opened_paths=paths,
        )
        with self._condition:
            self._opened_writers = list(result.failed_writers)
            self._opened_paths = list(result.failed_paths)
            self._cleanup_active = False
            self._cleanup_completed = result.succeeded
            self._condition.notify_all()
        if not result.succeeded:
            raise StateError(
                "Multipart staging resources could not be fully cleaned.",
                operation="api_routes.parse_streaming_multipart.cleanup",
                details={
                    "failed_writer_count": len(result.failed_writers),
                    "failed_path_count": len(result.failed_paths),
                },
            ) from result.first_failure

    def remove_path(self, path: str) -> None:
        with self._condition:
            remaining_paths = [
                opened_path for opened_path in self._opened_paths if opened_path != path
            ]
            self._opened_paths = remaining_paths
            if not self._opened_paths and not self._opened_writers:
                self._cleanup_completed = self._cleanup_requested

    def cleanup_path_immediately(self, path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            self.remove_path(path)
            return
        self.remove_path(path)
