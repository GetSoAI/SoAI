"""SoAI - Immutable provider descriptor snapshots for WebUI attachments [backend/features/api/runtime/webui_attachments/provider_descriptor_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import PayloadTooLargeError, PreconditionError, ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.content_snapshot import capture_file_snapshot
from core.files.temp_files import system_temp_directory
from core.filesystem.descriptor_io import open_descriptor
from core.logging.trace import get_logger
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

__all__ = (
    "ProviderDescriptorSnapshot",
    "close_provider_descriptor_snapshot",
    "load_provider_descriptor_snapshot",
)

LOGGER_NAME = "SoAI.features.api.provider_descriptor_snapshot"
OPERATION_PROVIDER_DESCRIPTOR_SNAPSHOT = "webui.attachments.provider_descriptor_snapshot"


@dataclass(frozen=True, slots=True)
class ProviderDescriptorSnapshot:
    descriptor: int
    temp_path: str


def _remove_temp_path(temp_path: str) -> None:
    try:
        os.remove(temp_path)
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to remove temporary WebUI provider snapshot.",
            operation=OPERATION_PROVIDER_DESCRIPTOR_SNAPSHOT,
            details={"temp_path": temp_path},
            level="debug",
        )


def _close_descriptor(descriptor: int, *, temp_path: str) -> None:
    try:
        os.close(descriptor)
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to close WebUI provider snapshot.",
            operation=OPERATION_PROVIDER_DESCRIPTOR_SNAPSHOT,
            details={"temp_path": temp_path},
            level="debug",
        )


def close_provider_descriptor_snapshot(snapshot: ProviderDescriptorSnapshot | None) -> None:
    if snapshot is None:
        return
    _close_descriptor(snapshot.descriptor, temp_path=snapshot.temp_path)
    _remove_temp_path(snapshot.temp_path)


def load_provider_descriptor_snapshot(
    *,
    source_descriptor: int,
    filename: str,
    expected_size_bytes: int,
    expected_sha256: str,
    deadline: MonotonicDeadline | None = None,
) -> ProviderDescriptorSnapshot | None:
    deadline = deadline or deadline_after(float(INTERACTIVE_TIMEOUT_SEC))
    try:
        snapshot = capture_file_snapshot(
            descriptor=source_descriptor,
            directory=system_temp_directory(),
            suffix=os.path.splitext(filename)[1],
            maximum_bytes=expected_size_bytes,
            expected_size=expected_size_bytes,
            expected_sha256=expected_sha256,
            deadline=deadline,
        )
        temp_path = snapshot.content.file_path
    except TimeoutError:
        raise
    except (OSError, ValidationError, PreconditionError, PayloadTooLargeError):
        return None
    snapshot_descriptor = -1
    completed = False
    try:
        snapshot_descriptor = open_descriptor(temp_path, os.O_RDONLY)
        content_hash = hash_descriptor_content(
            snapshot_descriptor, maximum_bytes=expected_size_bytes, deadline=deadline
        )
        if (
            content_hash.size_bytes != expected_size_bytes
            or content_hash.sha256_hex != expected_sha256
        ):
            return None
        completed = True
        return ProviderDescriptorSnapshot(descriptor=snapshot_descriptor, temp_path=temp_path)
    except TimeoutError:
        raise
    except (OSError, ValidationError):
        return None
    finally:
        if not completed:
            if snapshot_descriptor >= 0:
                _close_descriptor(snapshot_descriptor, temp_path=temp_path)
            _remove_temp_path(temp_path)
