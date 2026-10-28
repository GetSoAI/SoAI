"""SoAI - Stage accepted Windows installer diagnostic archives [backend/core/bootstrap/windows_installation_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from contextlib import ExitStack
from typing import TYPE_CHECKING

from core.bootstrap.install_payload_transaction import copy_install_entry, install_entry_copy_size
from core.bootstrap.install_target_windows import (
    retain_windows_install_ancestors,
    validate_windows_install_target,
)
from core.errors.exceptions import ConflictError, ValidationError
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.file_sync import fsync_install_entry
from core.filesystem.path_coercion import normalize_filesystem_path

__all__ = ("stage_windows_installation_diagnostics",)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol


def stage_windows_installation_diagnostics(
    installed_root: str,
    staging_root: str,
    reservation_provider: StorageManagerProtocol,
) -> None:
    if os.path.normcase(os.path.abspath(installed_root)) == os.path.normcase(
        os.path.abspath(staging_root)
    ):
        return
    source = os.path.join(installed_root, "installer-support")
    if not os.path.lexists(normalize_filesystem_path(source)):
        return
    validate_windows_install_target(source, create=False)
    with ExitStack() as resources:
        retain_windows_install_ancestors(source, resources)
        archives = tuple(
            os.path.join(source, name)
            for name in sorted(os.listdir(normalize_filesystem_path(source)))
            if name.casefold().startswith("install-diagnostics-")
            and name.casefold().endswith(".zip")
        )
        if not archives:
            return
        for archive in archives:
            attributes = os.stat(normalize_filesystem_path(archive), follow_symlinks=False)
            if not stat.S_ISREG(attributes.st_mode) or is_windows_reparse_point(attributes):
                raise ValidationError("Installed diagnostic archives must be regular files.")
        destination = os.path.join(staging_root, "installer-support")
        validate_windows_install_target(destination)
        retain_windows_install_ancestors(destination, resources)
        for archive in archives:
            target = os.path.join(destination, os.path.basename(archive))
            if os.path.lexists(normalize_filesystem_path(target)):
                raise ConflictError(
                    "Incoming application files conflict with retained installation diagnostics."
                )
        required_bytes = sum(install_entry_copy_size(archive) for archive in archives)
        with (
            reservation_provider.reserve_disk_space(
                path=destination,
                required_bytes=required_bytes,
                operation="core.bootstrap.install_windows.stage_diagnostics",
                details={"archive_count": len(archives)},
            ) as reservation,
            reservation.claim_write_bytes(required_bytes) as claim,
        ):
            for archive in archives:
                copy_install_entry(archive, destination)
            fsync_install_entry(destination)
            claim.commit()
