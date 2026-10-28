"""SoAI - Receipt-bound publication cleanup [backend/core/files/commit_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import StateError
from core.files.anchored_directory import (
    open_anchored_workspace,
    require_anchored_directory_identity,
)
from core.files.commit_receipt import FileCleanupIncompleteError, FileCommitReceipt
from core.files.content_errors import FileContentChangedError
from core.files.content_verification import require_descriptor_content
from core.files.file_identity import FileIdentity
from core.files.windows_anchored_directory import open_windows_anchored_directory
from core.files.windows_handle_operations import (
    close_windows_path_resources,
    mark_windows_file_descriptor_for_deletion,
)
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

__all__ = ("remove_committed_file",)


def remove_committed_file(receipt: FileCommitReceipt) -> None:
    with open_anchored_workspace(receipt.root_path) as root:
        if root.identity != receipt.root_identity:
            raise FileCleanupIncompleteError("The workspace changed; the saved file was retained.")
        if os.name != "nt":
            try:
                os.stat(receipt.destination_path, follow_symlinks=False)
            except FileNotFoundError:
                try:
                    require_anchored_directory_identity(receipt.root_path, receipt.root_identity)
                except (OSError, StateError) as exception:
                    raise FileCleanupIncompleteError(
                        "The workspace changed; automatic cleanup could not be verified."
                    ) from exception
                return
            raise FileCleanupIncompleteError(
                "The saved file was retained because this filesystem cannot atomically verify and remove it."
            )
        parent = open_windows_anchored_directory(os.path.dirname(receipt.destination_path))
        try:
            descriptor = -1
            try:
                descriptor = parent.open_file(
                    os.path.basename(receipt.destination_path), delete=True
                )
            except FileNotFoundError:
                return
            try:
                identity = FileIdentity.from_stat(os.fstat(descriptor))
                if not receipt.file_identity.matches_descriptor_snapshot(identity):
                    raise FileCleanupIncompleteError("The saved file changed and was retained.")
                try:
                    require_descriptor_content(
                        descriptor,
                        expected_size=receipt.file_identity.size,
                        expected_sha256=receipt.sha256_hex,
                        deadline=deadline_after(float(INTERACTIVE_TIMEOUT_SEC)),
                    )
                except FileContentChangedError as exception:
                    raise FileCleanupIncompleteError(
                        "The saved file content changed and was retained."
                    ) from exception
                mark_windows_file_descriptor_for_deletion(descriptor)
            finally:
                close_windows_path_resources(
                    [], leaf_file_descriptor=descriptor, primary_exception=sys.exception()
                )
            parent.flush()
        finally:
            parent.close()
