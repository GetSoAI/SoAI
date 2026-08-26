"""SoAI - Plugin safety validation caching and import scanning [backend/plugins/class_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from typing import TYPE_CHECKING

from filelock import Timeout

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    NotFoundError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.filesystem.async_queries import async_makedirs, async_path_exists
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from plugins.package_audit import audit_plugin_package
from plugins.path_safety import get_plugin_validation_cache_path
from plugins.security import ensure_import_tree_has_no_forbidden_imports

if TYPE_CHECKING:
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("validate_plugin_safety",)

LOGGER_NAME = "SoAI.plugins.class_validation"
OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_CACHE = "plugin_security.validate_plugin_cache"
OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_CACHE_WRITE = (
    "plugin_security.validate_plugin_cache_write"
)
OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_SAFETY = "plugin_security.validate_plugin_safety"


PLUGIN_VALIDATION_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    InsufficientDiskSpaceError,
    NotFoundError,
    SecurityError,
    StateError,
    SyntaxError,
    Timeout,
    ValidationError,
)


async def validate_plugin_safety(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    package_audit: PluginPackageAudit | None = None,
) -> tuple[bool, str]:
    logger = get_logger(LOGGER_NAME)
    async with manager.state.validation.validation_locks.lock(plugin_name):
        audit = package_audit
        if audit is None:
            try:
                audit = await audit_plugin_package(
                    manager,
                    plugin_name,
                    enforce_import_scan=False,
                    enforce_hash_policy=False,
                )
            except PLUGIN_VALIDATION_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Plugin source audit failed during safety validation (non-critical).",
                    operation=OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_SAFETY,
                    details={"plugin_name": plugin_name},
                    level="debug",
                )
                return (False, f"Validation failed: {exception}")
        current_hash = audit.archive_hash
        if not current_hash:
            return (False, "Could not calculate plugin hash")
        validation_cache_path = get_plugin_validation_cache_path(manager, plugin_name)
        validation_cache_lock_path = (
            manager.dependencies.infrastructure.config_manager.get_lock_path(validation_cache_path)
        )
        await async_makedirs(os.path.dirname(validation_cache_lock_path), exist_ok=True)
        try:
            async with async_guarded_file_lock(validation_cache_lock_path, timeout=5):
                if await async_path_exists(validation_cache_path):

                    def read_cache_file(path: str) -> str:
                        with open_text(path, encoding="utf-8") as cache_file:
                            return cache_file.read().strip()

                    cached_hash = await asyncio.to_thread(read_cache_file, validation_cache_path)
                    if cached_hash == current_hash:
                        return (True, "Previously validated")
        except PLUGIN_VALIDATION_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Plugin validation cache read failed; proceeding with full validation (non-critical).",
                operation=OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_CACHE,
                details={"plugin": plugin_name},
                level="debug",
            )
        try:
            if not audit.imports_validated:
                for python_member in audit.python_members:
                    ensure_import_tree_has_no_forbidden_imports(
                        plugin_name,
                        python_member.parsed_source,
                    )

            def writer(handle: io.TextIOBase) -> None:
                handle.write(current_hash)

            try:
                async with async_guarded_file_lock(validation_cache_lock_path, timeout=5):
                    await async_makedirs(os.path.dirname(validation_cache_path), exist_ok=True)
                    required_bytes = len(current_hash.encode("utf-8"))
                    with manager.dependencies.infrastructure.storage_manager.reserve_disk_space(
                        path=validation_cache_path,
                        required_bytes=required_bytes,
                        operation=OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_CACHE_WRITE,
                        details={
                            "plugin_name": plugin_name,
                            "required_bytes": required_bytes,
                        },
                    ) as reservation:
                        with claim_reserved_write(reservation, size_bytes=required_bytes):
                            await asyncio.to_thread(
                                atomic_write_text,
                                validation_cache_path,
                                writer,
                                ensure_parent=False,
                            )
            except PLUGIN_VALIDATION_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Plugin validation cache update failed; proceeding without cache (non-critical).",
                    operation=OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_CACHE_WRITE,
                    details={"plugin_name": plugin_name},
                    level="debug",
                )
            return (True, "Validation passed")
        except PLUGIN_VALIDATION_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Plugin safety validation failed (non-critical).",
                operation=OPERATION_PLUGIN_SECURITY_VALIDATE_PLUGIN_SAFETY,
                details={"plugin_name": plugin_name},
                level="debug",
            )
            return (False, f"Validation failed: {exception}")
