"""SoAI - Handle anchored Windows upload publication [backend/features/file_explorer/secure_ops/staged_upload_commit_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import io
import os
import sys
from typing import TYPE_CHECKING

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import FileCommitReceipt, FilePublicationUncertainError
from core.files.content_errors import FileContentChangedError
from core.files.content_snapshot import iter_snapshot_chunks
from core.files.content_verification import require_descriptor_content
from core.files.file_identity import FileIdentity
from core.files.staged_transfer import write_chunks_to_descriptor
from core.files.temp_files import create_secure_temp_binary_handle
from core.files.windows_anchored_directory import open_windows_anchored_directory
from core.files.windows_handle_operations import (
    close_windows_path_resources,
    mark_windows_file_descriptor_for_deletion,
)
from core.filesystem.file_sync import flush_and_fsync_file
from core.hardware.reservation_claims import claim_reserved_write
from features.file_explorer.secure_ops.staged_upload_commit_outcomes import (
    destination_exists_error,
    raise_if_cancelled,
    raise_if_commit_cancelled,
    raise_publication_failure,
    settle_upload_copy_resources,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.files.windows_anchored_directory import WindowsAnchoredDirectory
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("commit_windows_staged_upload",)


def commit_windows_staged_upload(
    *,
    source_path: str,
    destination_path: str,
    destination_root: str,
    expected_size: int,
    expected_sha256: str,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
    allow_symlinks: bool,
) -> FileCommitReceipt:
    _ = allow_symlinks
    published = False
    receipt: FileCommitReceipt | None = None
    try:
        root = open_windows_anchored_directory(destination_root)
        try:
            parent = open_windows_anchored_directory(os.path.dirname(destination_path))
            try:
                source_parent = open_windows_anchored_directory(os.path.dirname(source_path))
                try:
                    source = source_parent.open_file(
                        os.path.basename(source_path), delete=True, writable=True
                    )
                    try:
                        identity = FileIdentity.from_stat(os.fstat(source))
                        if not identity.is_regular_file or identity.size != expected_size:
                            raise FileContentChangedError(
                                "The staged file changed. Upload it again."
                            )
                        os.fsync(source)
                        raise_if_cancelled(token)
                        require_descriptor_content(
                            source,
                            expected_size=expected_size,
                            expected_sha256=expected_sha256,
                            cancellation=token,
                        )
                        copy_required = False
                        try:
                            parent.publish_file_descriptor(
                                source, os.path.basename(destination_path)
                            )
                        except FileExistsError as exception:
                            raise destination_exists_error(exception) from exception
                        except OSError as exception:
                            if exception.errno != errno.EXDEV:
                                raise
                            copy_required = True
                        else:
                            published = True
                            try:
                                parent.flush()
                                source_parent.flush()
                            except OSError as exception:
                                raise_publication_failure(exception, published=True)
                            verified = require_descriptor_content(
                                source,
                                expected_size=expected_size,
                                expected_sha256=expected_sha256,
                            )
                            receipt = FileCommitReceipt(
                                os.path.abspath(destination_root),
                                os.path.relpath(destination_path, destination_root),
                                root.identity,
                                verified,
                                expected_sha256,
                            )
                        if copy_required:
                            receipt = _copy_publish(
                                source,
                                parent,
                                destination_path,
                                destination_root,
                                root.identity,
                                expected_size,
                                token,
                                storage_manager,
                                expected_sha256,
                            )
                            published = True
                            mark_windows_file_descriptor_for_deletion(source)
                    finally:
                        close_windows_path_resources(
                            [], leaf_file_descriptor=source, primary_exception=sys.exception()
                        )
                    source_parent.flush()
                finally:
                    source_parent.close()
            finally:
                parent.close()
        finally:
            root.close()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise_publication_failure(exception, published=published)
    if receipt is None:
        raise FilePublicationUncertainError("The upload supplied no verified publication receipt.")
    raise_if_commit_cancelled(token, source_path, destination_path, receipt)
    return receipt


def _copy_publish(
    source: int,
    parent: WindowsAnchoredDirectory,
    destination: str,
    root: str,
    root_identity: tuple[int, int],
    expected_size: int,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
    expected_sha256: str,
) -> FileCommitReceipt:
    identity = FileIdentity.from_stat(os.fstat(source))
    if not identity.is_regular_file or identity.size != expected_size:
        raise FileContentChangedError("The staged file changed. Upload it again.")
    reservation = storage_manager.reserve_disk_space(
        path=os.path.dirname(destination),
        required_bytes=expected_size,
        operation="file_explorer.upload.commit_copy",
        details={"size_bytes": expected_size},
    )
    handle: io.BufferedRandom | None = None
    temporary_path: str | None = None
    descriptor = -1
    published = False
    try:
        handle, temporary_path = create_secure_temp_binary_handle(
            directory=os.path.dirname(destination),
            prefix=".soai-upload-",
            suffix=".partial",
            directory_authority=parent,
            delete_access=True,
        )
        descriptor = handle.fileno()
        content = write_chunks_to_descriptor(
            descriptor,
            iter_snapshot_chunks(source, identity, token, None),
            on_chunk_write_scope=lambda byte_count: claim_reserved_write(
                reservation, size_bytes=byte_count
            ),
            max_bytes=expected_size,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
        flush_and_fsync_file(handle)
        raise_if_cancelled(token)
        try:
            parent.publish_file_descriptor(descriptor, os.path.basename(destination))
        except FileExistsError as exception:
            raise destination_exists_error(exception) from exception
        published = True
        temporary_path = None
        written = FileIdentity.from_stat(os.fstat(descriptor))
        closing_handle = handle
        handle = None
        descriptor = -1
        closing_handle.close()
        parent.flush()
        descriptor = parent.open_file(os.path.basename(destination))
        final_identity = FileIdentity.from_stat(os.fstat(descriptor))
        if (written.device, written.inode, written.size) != (
            final_identity.device,
            final_identity.inode,
            final_identity.size,
        ):
            raise FilePublicationUncertainError("The published file changed during commit.")
        final_identity = require_descriptor_content(
            descriptor,
            expected_size=expected_size,
            expected_sha256=content.sha256_hex,
        )
        return FileCommitReceipt(
            os.path.abspath(root),
            os.path.relpath(destination, root),
            root_identity,
            final_identity,
            content.sha256_hex,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise_publication_failure(exception, published=published)
    finally:
        try:
            if handle is None and descriptor >= 0:
                close_windows_path_resources(
                    [], leaf_file_descriptor=descriptor, primary_exception=sys.exception()
                )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            raise_publication_failure(exception, published=published)
        finally:
            settle_upload_copy_resources(
                handle,
                reservation,
                published=published,
                temporary_path=temporary_path,
                delete_by_handle=True,
            )
