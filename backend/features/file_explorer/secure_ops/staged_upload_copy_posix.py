"""SoAI - Reserved POSIX upload copy publication [backend/features/file_explorer/secure_ops/staged_upload_copy_posix.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.content_snapshot import iter_snapshot_chunks
from core.files.file_identity import FileIdentity
from core.files.posix_anchored_directory import PosixAnchoredDirectory
from core.files.staged_transfer import write_chunks_to_descriptor
from core.files.temp_files import create_secure_temp_binary_handle
from core.filesystem.exclusive_rename import rename_file_without_replacement
from core.filesystem.file_sync import flush_and_fsync_file
from core.hardware.reservation_claims import claim_reserved_write
from features.file_explorer.secure_ops.staged_upload_commit_outcomes import (
    destination_exists_error,
    raise_if_cancelled,
    raise_publication_failure,
    settle_upload_copy_resources,
)
from features.file_explorer.secure_ops.staged_upload_destination import (
    fsync_destination_directory,
    verify_posix_upload_publication,
)
from features.file_explorer.secure_ops.staged_upload_source import remove_staged_source

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.files.commit_receipt import FileCommitReceipt
    from core.hardware.protocols_storage import StorageManagerProtocol
    from features.file_explorer.secure_ops.staged_upload_source import OpenedStagedSource

__all__ = ("copy_publish_posix_upload",)


def copy_publish_posix_upload(
    source: OpenedStagedSource,
    parent: int,
    destination_path: str,
    destination_root: str,
    root_identity: tuple[int, int],
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
    expected_sha256: str,
) -> FileCommitReceipt:
    identity = FileIdentity.from_stat(source.stat_result)
    reservation = storage_manager.reserve_disk_space(
        path=os.path.dirname(destination_path),
        required_bytes=identity.size,
        operation="file_explorer.upload.commit_copy",
        details={"size_bytes": identity.size},
    )
    handle: io.BufferedRandom | None = None
    temporary_path: str | None = None
    published = False
    try:
        handle, temporary_path = create_secure_temp_binary_handle(
            directory=os.path.dirname(destination_path),
            prefix=".soai-upload-",
            suffix=".partial",
            directory_authority=PosixAnchoredDirectory(parent),
        )
        write_chunks_to_descriptor(
            handle.fileno(),
            iter_snapshot_chunks(source.file_descriptor, identity, token, None),
            on_chunk_write_scope=lambda byte_count: claim_reserved_write(
                reservation, size_bytes=byte_count
            ),
            max_bytes=identity.size,
            expected_size=identity.size,
            expected_sha256=expected_sha256,
        )
        flush_and_fsync_file(handle)
        raise_if_cancelled(token)
        try:
            rename_file_without_replacement(
                os.path.basename(temporary_path),
                os.path.basename(destination_path),
                source_dir_fd=parent,
                destination_dir_fd=parent,
            )
        except FileExistsError as exception:
            raise destination_exists_error(exception) from exception
        published = True
        temporary_path = None
        remove_staged_source(source)
        fsync_destination_directory(source.parent_descriptor)
        fsync_destination_directory(parent)
        return verify_posix_upload_publication(
            destination_root,
            destination_path,
            root_identity,
            parent,
            FileIdentity.from_stat(os.fstat(handle.fileno())),
            expected_sha256,
            expected_size=identity.size,
            token=token,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise_publication_failure(exception, published=published)
    finally:
        settle_upload_copy_resources(
            handle,
            reservation,
            published=published,
            temporary_path=temporary_path,
        )
