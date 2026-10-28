"""SoAI - Platform selected anchored workspace directory access [backend/core/files/anchored_directory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from core.concurrency.deadlines import MonotonicDeadline
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError
from core.files.posix_anchored_directory import open_posix_anchored_directory
from core.files.protocols_anchored import AnchoredDirectoryProtocol
from core.files.windows_anchored_directory import open_windows_anchored_directory

__all__ = ("open_anchored_workspace", "require_anchored_directory_identity")


@contextmanager
def open_anchored_workspace(
    path: str,
    *,
    deadline: MonotonicDeadline | None = None,
    cancellation: CancellationTokenProtocol | None = None,
) -> Generator[AnchoredDirectoryProtocol]:
    directory: AnchoredDirectoryProtocol
    if os.name == "nt":
        directory = open_windows_anchored_directory(
            path, deadline=deadline, cancellation=cancellation
        )
    else:
        directory = open_posix_anchored_directory(path)
    try:
        yield directory
    finally:
        directory.close()


def require_anchored_directory_identity(path: str, expected: tuple[int, int]) -> None:
    with open_anchored_workspace(path) as current:
        if current.identity != expected:
            raise StateError("The staging directory changed during file capture.")
