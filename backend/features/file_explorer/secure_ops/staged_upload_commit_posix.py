"""SoAI - POSIX staged upload publication [backend/features/file_explorer/secure_ops/staged_upload_commit_posix.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.anchored_directory import open_anchored_workspace
from core.files.commit_receipt import FileCommitReceipt, FilePublicationUncertainError
from core.files.content_errors import FileContentChangedError
from core.files.content_verification import require_descriptor_content
from core.files.file_identity import FileIdentity
from core.files.managed_storage_traversal import close_file_descriptor_stack
from features.file_explorer.secure_ops.staged_upload_commit_outcomes import (
    destination_exists_error,
    raise_if_cancelled,
    raise_if_commit_cancelled,
    raise_publication_failure,
)
from features.file_explorer.secure_ops.staged_upload_copy_posix import copy_publish_posix_upload
from features.file_explorer.secure_ops.staged_upload_destination import (
    fsync_destination_directory,
    open_pinned_destination_directory,
    verify_posix_upload_publication,
)
from features.file_explorer.secure_ops.staged_upload_source import (
    OpenedStagedSource,
    close_staged_source,
    open_staged_source,
    remove_staged_source,
    same_staged_file_identity,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("commit_posix_staged_upload",)


def commit_posix_staged_upload(
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
    receipt: FileCommitReceipt | None = None
    try:
        with open_anchored_workspace(destination_root) as root:
            parent = open_pinned_destination_directory(
                destination_root, os.path.dirname(destination_path), allow_symlinks=allow_symlinks
            )
            try:
                source = open_staged_source(source_path, expected_size=expected_size)
                try:
                    receipt = _publish(
                        source,
                        parent,
                        destination_path,
                        destination_root,
                        root.identity,
                        token,
                        storage_manager,
                        expected_sha256,
                    )
                finally:
                    close_staged_source(source)
            finally:
                close_file_descriptor_stack([parent])
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise_publication_failure(exception, published=receipt is not None)
    if receipt is None:
        raise FilePublicationUncertainError("The upload supplied no verified publication receipt.")
    raise_if_commit_cancelled(token, source_path, destination_path, receipt)
    return receipt


def _publish(
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
    os.fsync(source.file_descriptor)
    raise_if_cancelled(token)
    if identity.device == os.fstat(parent).st_dev:
        require_descriptor_content(
            source.file_descriptor,
            expected_size=identity.size,
            expected_sha256=expected_sha256,
            cancellation=token,
        )
    if not identity.matches_descriptor_snapshot(
        FileIdentity.from_stat(os.fstat(source.file_descriptor))
    ):
        raise FileContentChangedError("The staged file changed. Upload it again.")
    name = os.path.basename(destination_path)
    copy_required = False
    try:
        _link_staged_source(source, name, parent)
    except FileExistsError as exception:
        raise destination_exists_error(exception) from exception
    except OSError as exception:
        if exception.errno in {errno.EEXIST, errno.EISDIR}:
            raise destination_exists_error(exception) from exception
        if exception.errno not in {errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS}:
            raise
        copy_required = True
    if copy_required:
        return copy_publish_posix_upload(
            source,
            parent,
            destination_path,
            destination_root,
            root_identity,
            token,
            storage_manager,
            expected_sha256,
        )
    try:
        published = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            published.st_dev != identity.device
            or published.st_ino != identity.inode
            or published.st_mode != identity.mode
            or published.st_size != identity.size
            or published.st_mtime_ns != identity.modified_ns
        ):
            raise FileContentChangedError("The destination changed during publication.")
        remove_staged_source(source)
        fsync_destination_directory(source.parent_descriptor)
        fsync_destination_directory(parent)
        final_identity = FileIdentity.from_stat(os.fstat(source.file_descriptor))
        return verify_posix_upload_publication(
            destination_root,
            destination_path,
            root_identity,
            parent,
            final_identity,
            expected_sha256,
            expected_size=identity.size,
            token=token,
        )
    except (OSError, SoAIError) as exception:
        raise FilePublicationUncertainError(
            "File publication could not be verified."
        ) from exception


def _link_staged_source(
    source: OpenedStagedSource, destination_name: str, destination_descriptor: int
) -> None:
    os.link(
        source.filename,
        destination_name,
        src_dir_fd=source.parent_descriptor,
        dst_dir_fd=destination_descriptor,
        follow_symlinks=False,
    )
    try:
        published = os.stat(destination_name, dir_fd=destination_descriptor, follow_symlinks=False)
    except OSError as exception:
        raise_publication_failure(exception, published=True)
    if not same_staged_file_identity(published, source.stat_result):
        raise FilePublicationUncertainError(
            "The source changed during publication; the destination was retained."
        )
