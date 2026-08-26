"""SoAI - Cleanup helpers for streaming multipart staging [backend/features/api/routes/upload_streaming_multipart_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from features.api.routes.internal_protocols import MultipartStagingWriter

__all__ = ("MultipartCleanupResult", "cleanup_staged_multipart_upload")


@dataclass(frozen=True, slots=True)
class MultipartCleanupResult:
    failed_writers: tuple[MultipartStagingWriter, ...]
    failed_paths: tuple[str, ...]
    first_failure: Exception | None

    @property
    def succeeded(self) -> bool:
        return not self.failed_writers and not self.failed_paths


def cleanup_staged_multipart_upload(
    *,
    opened_writers: list[MultipartStagingWriter],
    opened_paths: list[str],
) -> MultipartCleanupResult:
    failed_writers: list[MultipartStagingWriter] = []
    failed_paths: list[str] = []
    first_failure: Exception | None = None
    for writer in opened_writers:
        try:
            writer.close()
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failed_writers.append(writer)
            if first_failure is None:
                first_failure = exception
    for staged_path in opened_paths:
        try:
            os.remove(staged_path)
        except FileNotFoundError:
            continue
        except OSError as exception:
            failed_paths.append(staged_path)
            if first_failure is None:
                first_failure = exception
    return MultipartCleanupResult(
        failed_writers=tuple(failed_writers),
        failed_paths=tuple(failed_paths),
        first_failure=first_failure,
    )
