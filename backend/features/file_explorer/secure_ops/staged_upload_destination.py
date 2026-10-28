"""SoAI - Pinned staged upload destination ownership [backend/features/file_explorer/secure_ops/staged_upload_destination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError, ValidationError
from core.files.commit_receipt import FileCommitReceipt, FilePublicationUncertainError
from core.files.content_verification import require_descriptor_content
from core.files.file_identity import FileIdentity
from core.files.managed_storage_traversal import close_file_descriptor_stack
from core.files.secure_open_flags import secure_read_only_open_flags
from core.filesystem.descriptor_io import open_descriptor
from features.file_explorer.secure_ops.link_checks import is_no_symlink_open_error

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "verify_posix_upload_publication",
    "fsync_destination_directory",
    "open_pinned_destination_directory",
)


def open_pinned_destination_directory(
    destination_root: str,
    destination_parent: str,
    *,
    allow_symlinks: bool,
) -> int:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    if allow_symlinks:
        return open_descriptor(destination_parent, directory_flags)
    directory_flags |= os.O_NOFOLLOW
    root = os.path.abspath(destination_root)
    parent = os.path.abspath(destination_parent)
    current_descriptor = open_descriptor(root, directory_flags)
    descriptor_returned = False
    try:
        relative_parent = os.path.relpath(parent, root)
        if relative_parent == ".":
            descriptor_returned = True
            return current_descriptor
        for path_component in relative_parent.split(os.sep):
            try:
                next_descriptor = open_descriptor(
                    path_component,
                    directory_flags,
                    dir_fd=current_descriptor,
                )
            except OSError as exception:
                component_stat = os.stat(
                    path_component,
                    dir_fd=current_descriptor,
                    follow_symlinks=False,
                )
                if stat.S_ISLNK(component_stat.st_mode) or is_no_symlink_open_error(exception):
                    raise SecurityError(
                        "Upload destination contains a symbolic link."
                    ) from exception
                if not stat.S_ISDIR(component_stat.st_mode):
                    raise ValidationError(
                        "Upload destination parent path is not a directory."
                    ) from exception
                raise
            previous_descriptor = current_descriptor
            current_descriptor = next_descriptor
            close_file_descriptor_stack([previous_descriptor])
        descriptor_returned = True
        return current_descriptor
    finally:
        if not descriptor_returned:
            close_file_descriptor_stack([current_descriptor])


def fsync_destination_directory(directory_descriptor: int) -> None:
    os.fsync(directory_descriptor)


def verify_posix_upload_publication(
    root: str,
    destination: str,
    root_identity: tuple[int, int],
    parent: int,
    identity: FileIdentity,
    digest: str,
    *,
    expected_size: int,
    token: CancellationTokenProtocol,
) -> FileCommitReceipt:
    descriptor = open_descriptor(
        os.path.basename(destination),
        secure_read_only_open_flags(directory=False),
        dir_fd=parent,
    )
    try:
        if not identity.matches_descriptor_snapshot(FileIdentity.from_stat(os.fstat(descriptor))):
            raise FilePublicationUncertainError("The published file changed during commit.")
        verified = require_descriptor_content(
            descriptor, expected_size=expected_size, expected_sha256=digest, cancellation=token
        )
        root_stat = os.stat(root, follow_symlinks=False)
        parent_stat = os.stat(os.path.dirname(destination), follow_symlinks=False)
        pinned_parent = os.fstat(parent)
        final = FileIdentity.from_stat(
            os.stat(os.path.basename(destination), dir_fd=parent, follow_symlinks=False)
        )
        if (
            (root_stat.st_dev, root_stat.st_ino) != root_identity
            or (parent_stat.st_dev, parent_stat.st_ino)
            != (pinned_parent.st_dev, pinned_parent.st_ino)
            or not verified.matches_descriptor_snapshot(final)
        ):
            raise FilePublicationUncertainError(
                "The workspace or published file changed during commit."
            )
        return FileCommitReceipt(
            os.path.abspath(root),
            os.path.relpath(destination, root),
            root_identity,
            verified,
            digest,
        )
    finally:
        close_file_descriptor_stack([descriptor])
