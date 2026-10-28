"""SoAI - Bounded descriptor content authority verification [backend/core/files/content_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.files.content_errors import FileContentChangedError
from core.files.content_hashing import hash_descriptor_content
from core.files.file_identity import FileIdentity

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = ("require_descriptor_content", "verify_descriptor_content")


def require_descriptor_content(
    descriptor: int,
    *,
    expected_size: int,
    expected_sha256: str,
    cancellation: CancellationTokenProtocol | None = None,
    deadline: MonotonicDeadline | None = None,
) -> FileIdentity:
    if cancellation is not None:
        cancellation.raise_if_cancelled()
    before = FileIdentity.from_stat(os.fstat(descriptor))
    if not before.is_regular_file or before.size != expected_size:
        raise FileContentChangedError("The file no longer has its accepted type or size.")
    content = hash_descriptor_content(
        descriptor, maximum_bytes=expected_size, cancellation=cancellation, deadline=deadline
    )
    after = FileIdentity.from_stat(os.fstat(descriptor))
    if (
        content.size_bytes != expected_size
        or content.sha256_hex != expected_sha256
        or not before.matches_descriptor_snapshot(after)
    ):
        raise FileContentChangedError("The file no longer matches its accepted content.")
    if cancellation is not None:
        cancellation.raise_if_cancelled()
    return after


async def verify_descriptor_content(
    descriptor: int,
    *,
    expected_size: int,
    expected_sha256: str,
    pool: BoundedBlockingPool,
    deadline: MonotonicDeadline,
) -> None:
    await run_joined_thread_call(
        partial(
            require_descriptor_content,
            descriptor,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            deadline=deadline,
        ),
        task_name="file-content-verification",
        pool=pool,
        admission_deadline=deadline,
        retain_resources_until_complete=True,
    )
