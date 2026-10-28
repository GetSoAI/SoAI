"""SoAI - Bounded immutable descriptor content capture [backend/core/files/content_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.files.anchored_directory import (
    open_anchored_workspace,
)
from core.files.content_errors import FileContentChangedError
from core.files.content_hashing import ContentHashResult, hash_descriptor_content
from core.files.descriptor_reading import read_descriptor_at
from core.files.file_identity import FileIdentity
from core.files.staged_transfer import (
    STAGED_TRANSFER_CHUNK_SIZE,
    StagedTransferResult,
    stage_chunks_to_temp_file,
)
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = ("FileSnapshot", "capture_file_snapshot", "iter_snapshot_chunks")


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    source_identity: FileIdentity
    content: StagedTransferResult


def _capture_checkpoint(
    cancellation: CancellationTokenProtocol | None, deadline: MonotonicDeadline | None
) -> None:
    if cancellation is not None:
        cancellation.raise_if_cancelled()
    if deadline is not None and deadline.expired():
        raise TimeoutError("File capture exceeded its operation deadline.")


def iter_snapshot_chunks(
    descriptor: int,
    identity: FileIdentity,
    cancellation: CancellationTokenProtocol | None,
    deadline: MonotonicDeadline | None,
) -> Iterator[bytes]:
    offset = 0
    while True:
        _capture_checkpoint(cancellation, deadline)
        chunk = read_descriptor_at(
            descriptor, min(STAGED_TRANSFER_CHUNK_SIZE, identity.size - offset + 1), offset
        )
        if not chunk:
            break
        yield chunk
        offset += len(chunk)
    _capture_checkpoint(cancellation, deadline)
    if not identity.matches_descriptor_snapshot(FileIdentity.from_stat(os.fstat(descriptor))):
        raise FileContentChangedError(
            "The source file changed while being copied. Select it again."
        )


def capture_file_snapshot(
    *,
    descriptor: int,
    directory: str,
    suffix: str,
    maximum_bytes: int,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    cancellation: CancellationTokenProtocol | None = None,
    deadline: MonotonicDeadline | None = None,
    on_chunk_write_scope: Callable[[int], AbstractContextManager[None]] | None = None,
    durability: Literal["temporary", "file", "directory"] = "file",
) -> FileSnapshot:
    require_non_negative_int_strict(
        maximum_bytes, error_message="File capture requires a nonnegative byte limit."
    )
    if expected_size is not None:
        require_non_negative_int_strict(
            expected_size, error_message="Expected snapshot size must be nonnegative."
        )
    _capture_checkpoint(cancellation, deadline)
    identity = FileIdentity.from_stat(os.fstat(descriptor))
    if not identity.is_regular_file:
        raise ValidationError("Only a regular file can be captured.")
    if identity.size > maximum_bytes:
        raise PayloadTooLargeError("The source file exceeds the permitted capture size.")
    if expected_size is not None and identity.size != expected_size:
        raise FileContentChangedError("The source file size changed. Select it again.")
    staging_directory = (
        os.path.abspath(directory) if durability == "directory" else os.path.realpath(directory)
    )

    def verify_source_content(content: ContentHashResult) -> None:
        _capture_checkpoint(cancellation, deadline)
        current_content = hash_descriptor_content(
            descriptor,
            maximum_bytes=maximum_bytes,
            cancellation=cancellation,
            deadline=deadline,
        )
        if current_content != content or not identity.matches_descriptor_snapshot(
            FileIdentity.from_stat(os.fstat(descriptor))
        ):
            raise FileContentChangedError(
                "The source file changed while being copied. Select it again."
            )
        _capture_checkpoint(cancellation, deadline)

    with open_anchored_workspace(
        staging_directory, deadline=deadline, cancellation=cancellation
    ) as authority:
        content = stage_chunks_to_temp_file(
            iter_snapshot_chunks(descriptor, identity, cancellation, deadline),
            temp_dir=staging_directory,
            suffix=suffix,
            on_chunk_write_scope=(
                on_chunk_write_scope
                if on_chunk_write_scope is not None
                else lambda byte_count: nullcontext()
            ),
            max_bytes=maximum_bytes,
            expected_size=identity.size,
            expected_sha256=expected_sha256,
            durability=durability,
            directory_authority=authority,
            verify_source_content=verify_source_content,
        )
        return FileSnapshot(source_identity=identity, content=content)
