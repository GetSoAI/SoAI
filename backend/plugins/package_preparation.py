"""SoAI - Content-addressed plugin package preparation [backend/plugins/package_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
import shutil
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.archives.zip_plan_extraction import extract_validated_zip_plan
from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
    uncancel_then_cleanup,
)
from core.errors.exceptions import StateError, ValidationError
from core.files.content_hashing import hash_seekable_binary_stream_content
from core.files.locking import async_guarded_file_lock
from core.files.temp_files import create_persistent_staging_directory
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.hardware.reservation_claims import claim_reserved_write
from plugins.fs_permissions import ensure_correct_permissions
from plugins.package_archive import open_validated_plugin_package
from plugins.package_audit import PluginPackageAudit
from plugins.package_completion import (
    build_plugin_package_completion_record,
    plugin_package_cache_matches,
    serialize_plugin_package_completion_record,
)
from plugins.package_paths import (
    COMPLETION_RECORD_NAME,
    get_plugin_package_cache_lock_target,
    get_plugin_package_hash_directory,
    get_plugin_package_hash_lock_target,
)

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("PreparedPluginPackage", "prepare_plugin_package")


@dataclass(frozen=True, slots=True)
class PreparedPluginPackage:
    plugin_name: str
    archive_hash: str
    package_root: str
    entrypoint_path: str


def _completion_text(audit: PluginPackageAudit) -> str:
    return serialize_plugin_package_completion_record(
        build_plugin_package_completion_record(audit),
    )


def _is_complete(package_root: str, audit: PluginPackageAudit) -> bool:
    return plugin_package_cache_matches(package_root, audit)


def _write_completion_record(staging_directory: str, completion_text: str) -> None:
    completion_path = os.path.join(staging_directory, COMPLETION_RECORD_NAME)

    def writer(file_handle: io.TextIOBase) -> None:
        file_handle.write(completion_text)

    atomic_write_text(completion_path, writer, ensure_parent=False)


def _extract_package_snapshot(
    audit: PluginPackageAudit,
    staging_directory: str,
) -> None:
    with open_regular_binary_no_symlink(
        audit.archive_path,
        not_found_message="Plugin package disappeared after audit.",
        symlink_message="Plugin package became a symbolic link after audit.",
        open_message="Plugin package could not be reopened after audit.",
        inspect_message="Plugin package could not be inspected after audit.",
        regular_file_message="Plugin package is no longer a regular file.",
    ) as file_handle:
        current_hash = hash_seekable_binary_stream_content(file_handle).sha256_hex
        if current_hash != audit.archive_hash:
            raise StateError(
                f"Plugin package for '{audit.plugin_name}' changed after audit.",
            )
        try:
            with open_validated_plugin_package(file_handle) as (zip_file, plan):
                current_summary = tuple(
                    (member.archive_path, member.file_size, member.zip_info.CRC)
                    for member in plan.members
                )
                audited_summary = tuple(
                    (member.archive_path, member.file_size, member.zip_info.CRC)
                    for member in audit.zip_plan.members
                )
                if current_summary != audited_summary:
                    raise StateError(
                        f"Plugin package for '{audit.plugin_name}' changed after audit.",
                    )
                extract_validated_zip_plan(zip_file, plan, staging_directory)
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as exception:
            raise ValidationError(
                "Plugin package ZIP snapshot could not be extracted."
            ) from exception


async def _prepare_hash_directory(
    manager: PluginManagerRuntimeProtocol,
    audit: PluginPackageAudit,
    package_root: str,
    entrypoint_path: str,
    package_cache_directory: str,
) -> PreparedPluginPackage:
    if _is_complete(package_root, audit):
        return PreparedPluginPackage(
            plugin_name=audit.plugin_name,
            archive_hash=audit.archive_hash,
            package_root=package_root,
            entrypoint_path=entrypoint_path,
        )
    if os.path.lexists(package_root):
        if os.path.isdir(package_root) and not os.path.islink(package_root):
            removal = asyncio.to_thread(shutil.rmtree, package_root)
        else:
            removal = asyncio.to_thread(os.unlink, package_root)
        await uncancel_and_wait(removal)
        if current_task_has_pending_cancellation():
            raise asyncio.CancelledError
    os.makedirs(package_cache_directory, exist_ok=True)
    staging_directory = create_persistent_staging_directory(
        prefix=f".staging.{audit.archive_hash}.",
        directory=package_cache_directory,
    )
    completion_text = _completion_text(audit)
    completion_bytes = len(completion_text.encode("utf-8"))
    required_bytes = audit.expanded_size + completion_bytes
    try:
        with manager.dependencies.infrastructure.storage_manager.reserve_disk_space(
            path=package_cache_directory,
            required_bytes=required_bytes,
            operation="plugins.package_preparation.prepare",
            details={
                "plugin_name": audit.plugin_name,
                "archive_hash": audit.archive_hash,
                "required_bytes": required_bytes,
            },
        ) as reservation:
            with claim_reserved_write(reservation, size_bytes=required_bytes):
                await uncancel_and_wait(
                    asyncio.to_thread(
                        _extract_package_snapshot,
                        audit,
                        staging_directory,
                    )
                )
                if current_task_has_pending_cancellation():
                    raise asyncio.CancelledError
                staged_entrypoint = os.path.join(staging_directory, "__init__.py")
                if os.path.islink(staged_entrypoint) or not os.path.isfile(staged_entrypoint):
                    raise StateError("Prepared plugin package entrypoint is not a regular file.")
                await uncancel_and_wait(ensure_correct_permissions(staging_directory))
                if current_task_has_pending_cancellation():
                    raise asyncio.CancelledError
                await uncancel_and_wait(
                    asyncio.to_thread(
                        _write_completion_record,
                        staging_directory,
                        completion_text,
                    )
                )
                if current_task_has_pending_cancellation():
                    raise asyncio.CancelledError
                os.rename(staging_directory, package_root)
    finally:
        if os.path.lexists(staging_directory):
            await uncancel_then_cleanup(
                asyncio.to_thread(shutil.rmtree, staging_directory),
            )
    return PreparedPluginPackage(
        plugin_name=audit.plugin_name,
        archive_hash=audit.archive_hash,
        package_root=package_root,
        entrypoint_path=entrypoint_path,
    )


async def prepare_plugin_package(
    manager: PluginManagerRuntimeProtocol,
    audit: PluginPackageAudit,
) -> PreparedPluginPackage:
    package_root = get_plugin_package_hash_directory(
        manager.paths.temp_directory,
        audit.plugin_name,
        audit.archive_hash,
    )
    entrypoint_path = os.path.join(package_root, "__init__.py")
    package_cache_directory = os.path.dirname(package_root)
    config_manager = manager.dependencies.infrastructure.config_manager
    cache_lock_path = config_manager.get_lock_path(
        get_plugin_package_cache_lock_target(
            manager.paths.temp_directory,
            audit.plugin_name,
        )
    )
    hash_lock_path = config_manager.get_lock_path(
        get_plugin_package_hash_lock_target(
            manager.paths.temp_directory,
            audit.plugin_name,
            audit.archive_hash,
        )
    )
    os.makedirs(os.path.dirname(cache_lock_path), exist_ok=True)
    async with async_guarded_file_lock(cache_lock_path, timeout=120):
        packages_root = os.path.dirname(package_cache_directory)
        if os.path.islink(packages_root) or (
            os.path.lexists(packages_root) and not os.path.isdir(packages_root)
        ):
            await uncancel_and_wait(asyncio.to_thread(os.unlink, packages_root))
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError
        os.makedirs(packages_root, exist_ok=True)
        if os.path.islink(package_cache_directory) or (
            os.path.lexists(package_cache_directory) and not os.path.isdir(package_cache_directory)
        ):
            await uncancel_and_wait(asyncio.to_thread(os.unlink, package_cache_directory))
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError
        os.makedirs(package_cache_directory, exist_ok=True)
        async with async_guarded_file_lock(hash_lock_path, timeout=120):
            return await _prepare_hash_directory(
                manager,
                audit,
                package_root,
                entrypoint_path,
                package_cache_directory,
            )
