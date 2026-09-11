"""SoAI - Update transaction state helpers [backend/app/updater/software_update/install_transaction_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.copy_no_symlinks.constants import UPDATER_EXCLUSIONS
from app.installation_transaction_admission import (
    TRANSACTION_CLEANUP_PREFIX,
    TRANSACTION_PREFIX,
    guard_installation_transaction_admission,
)
from core.bootstrap.install_payload import INSTALL_MANIFEST_FILENAME, MANAGED_DOCUMENT_ENTRIES
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.temp_files import create_secure_temp_directory
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.logging.protocols import LoggerProtocol
from core.runtime.process_identity import SOAI_BACKEND_MAIN_SUBPATH

__all__ = (
    "AppliedUpdateTransaction",
    "UpdateTransactionPaths",
    "allocate_update_transaction",
    "cleanup_update_transaction",
    "build_rollback_top_level_ignore_patterns",
    "build_update_extraction_top_level_ignore_patterns",
    "build_update_top_level_ignore_patterns",
    "is_preserved_top_level_item",
    "marker_path",
    "paths_from_transaction_directory",
    "remove_marker",
    "required_update_paths",
    "validate_transaction_markers",
    "write_marker",
)

OPERATION_CLEANUP_UPDATE_TRANSACTION = "application_updater.cleanup_update_transaction"

TRANSACTION_DISPOSAL_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    OSError,
    ConflictError,
    SecurityError,
    StateError,
    ValidationError,
)

STAGED_NEW_DIR = "new"
ROLLBACK_OLD_DIR = "old"
ROLLBACK_REQUIRED_MARKER = "rollback_required"
PREPARING_MARKER = "preparing"
OLD_COMPLETE_MARKER = "old_complete"
NEW_COMPLETE_MARKER = "new_complete"
SUCCESS_COMPLETE_MARKER = "success_complete"
ACTIVATION_FAILED_MARKER = "activation_failed"
ROLLBACK_COMPLETE_MARKER = "rollback_complete"
ROLLBACK_INVENTORY_REQUIRED_MARKER = "rollback_inventory_required"
DATA_PARENT_WAS_ABSENT_MARKER = "data_parent_was_absent"
CONFIG_PARENT_WAS_ABSENT_MARKER = "config_parent_was_absent"
MANAGED_DATA_PARENT = "data"
MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS = (
    MANAGED_DATA_PARENT,
    "config",
    "config.default.yaml",
)
MANAGED_VENDOR_RELATIVE_COMPONENTS = (MANAGED_DATA_PARENT, "vendor")
MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS = (INSTALL_MANIFEST_FILENAME,)
MANAGED_ROLLBACK_DIR = "managed"
CORE_REQUIRED_UPDATE_PATHS = (
    "VERSION",
    "release-info-v1.json",
    SOAI_BACKEND_MAIN_SUBPATH,
    "backend/core/meta/version.py",
    "frontend/index.html",
    "frontend/detached.html",
    "frontend/assets/build/manifest.json",
    "plugins/external.soaiplugin",
    "plugins/ollama.soaiplugin",
    "plugins/vllm.soaiplugin",
    "plugins/llamacpp.soaiplugin",
    "plugins/ctranslate2.soaiplugin",
    "plugins/embedding.soaiplugin",
    "plugins/whisper.soaiplugin",
    "plugins/melotts.soaiplugin",
    *MANAGED_DOCUMENT_ENTRIES,
)
EXECUTABLE_UPDATE_FILES = (
    "install-soai-macos.command",
    "install-soai-linux.sh",
    "soai.command",
    "soai.sh",
    "install-soai-from-release.command",
    "install-soai-from-release.sh",
    "uninstall-soai-linux.sh",
)
UPDATE_COMPONENT_IGNORE_PATTERNS = ("__pycache__", "*.pyc", "node_modules")


@dataclass(frozen=True, slots=True)
class UpdateTransactionPaths:
    base_path: str
    transaction_path: str
    staged_new_path: str
    rollback_old_path: str


@dataclass(frozen=True, slots=True)
class AppliedUpdateTransaction:
    base_path: str
    transaction_path: str


def build_update_top_level_ignore_patterns() -> tuple[str, ...]:
    return tuple(sorted(UPDATER_EXCLUSIONS))


def build_update_extraction_top_level_ignore_patterns() -> tuple[str, ...]:
    return tuple(
        sorted(pattern for pattern in UPDATER_EXCLUSIONS if pattern != MANAGED_DATA_PARENT)
    )


def build_rollback_top_level_ignore_patterns(transaction_path: str) -> tuple[str, ...]:
    _ = transaction_path
    return tuple(sorted(UPDATER_EXCLUSIONS))


def is_preserved_top_level_item(
    item_name: str,
    top_level_ignore_patterns: tuple[str, ...],
) -> bool:
    if item_name.startswith((TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX)):
        return True
    return any(fnmatch.fnmatch(item_name, pattern) for pattern in top_level_ignore_patterns)


def required_update_paths(platform_id: str) -> tuple[str, ...]:
    managed_config_default_path = "/".join(MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS)
    managed_vendor_metadata_path = "/".join(
        (*MANAGED_VENDOR_RELATIVE_COMPONENTS, "tika", "pyproject.toml")
    )
    platform_paths: tuple[str, ...]
    if platform_id in {"linux-x64", "linux-arm64"}:
        platform_paths = (
            "install-soai-linux.sh",
            "soai.sh",
            "install-soai-from-release.sh",
            "uninstall-soai-linux.sh",
            "backend/core/bootstrap/launcher_posix/update_recovery.sh",
        )
    elif platform_id in {"darwin-x64", "darwin-arm64"}:
        platform_paths = (
            "install-soai-macos.command",
            "soai.sh",
            "soai.command",
            "install-soai-from-release.sh",
            "install-soai-from-release.command",
            "backend/core/bootstrap/launcher_posix/update_recovery.sh",
        )
    elif platform_id == "windows-x64":
        platform_paths = (
            "install-soai-windows.ps1",
            "soai.exe",
            "install-soai-from-release.bat",
            "Microsoft.Web.WebView2.Core.dll",
            "Microsoft.Web.WebView2.WinForms.dll",
            "WebView2Loader.dll",
            "installer-support/release-info.json",
            "installer-support/installed-files.txt",
        )
    else:
        raise ValueError(f"Unsupported update platform: {platform_id}")
    return (
        *CORE_REQUIRED_UPDATE_PATHS,
        managed_config_default_path,
        managed_vendor_metadata_path,
        *platform_paths,
    )


def marker_path(transaction_path: str, marker_name: str) -> str:
    return os.path.join(transaction_path, marker_name)


def write_marker(transaction_path: str, marker_name: str) -> None:
    atomic_write_text_content(
        marker_path(transaction_path, marker_name),
        marker_name,
        ensure_parent=False,
        fsync=True,
        fsync_parent_directory=True,
    )


def validate_transaction_markers(transaction_path: str) -> None:
    for marker_name in (
        ROLLBACK_REQUIRED_MARKER,
        PREPARING_MARKER,
        OLD_COMPLETE_MARKER,
        NEW_COMPLETE_MARKER,
        SUCCESS_COMPLETE_MARKER,
        ACTIVATION_FAILED_MARKER,
        ROLLBACK_COMPLETE_MARKER,
        ROLLBACK_INVENTORY_REQUIRED_MARKER,
        DATA_PARENT_WAS_ABSENT_MARKER,
        CONFIG_PARENT_WAS_ABSENT_MARKER,
    ):
        path = marker_path(transaction_path, marker_name)
        if not os.path.lexists(path):
            continue
        if os.path.islink(path) or not os.path.isfile(path):
            raise StateError("Update phase marker is not a regular file; preserve it for repair.")
        if read_regular_file_no_symlink(path, max_bytes=128) != marker_name.encode("utf-8"):
            raise StateError("Update phase marker is corrupt; preserve it for repair.")
    if os.path.exists(marker_path(transaction_path, SUCCESS_COMPLETE_MARKER)) and any(
        os.path.exists(marker_path(transaction_path, marker))
        for marker in (ROLLBACK_COMPLETE_MARKER, ACTIVATION_FAILED_MARKER)
    ):
        raise StateError("Update terminal phases conflict; preserve the transaction for repair.")


def remove_marker(transaction_path: str, marker_name: str) -> None:
    path = marker_path(transaction_path, marker_name)
    if os.path.exists(path):
        os.remove(path)


def allocate_update_transaction(base_path: str) -> UpdateTransactionPaths:
    resolved_base_path = os.path.abspath(base_path)
    with guard_installation_transaction_admission(resolved_base_path):
        transaction_path = create_secure_temp_directory(
            prefix=TRANSACTION_PREFIX,
            directory=resolved_base_path,
        )
        staged_new_path = os.path.join(transaction_path, STAGED_NEW_DIR)
        rollback_old_path = os.path.join(transaction_path, ROLLBACK_OLD_DIR)
        try:
            os.makedirs(staged_new_path, mode=0o700, exist_ok=False)
            os.makedirs(rollback_old_path, mode=0o700, exist_ok=False)
        except OSError:
            for created_path in (rollback_old_path, staged_new_path, transaction_path):
                if os.path.isdir(created_path):
                    os.rmdir(created_path)
            raise
        fsync_directory(transaction_path, strict=True)
        fsync_directory(resolved_base_path, strict=True)
        return UpdateTransactionPaths(
            base_path=resolved_base_path,
            transaction_path=transaction_path,
            staged_new_path=staged_new_path,
            rollback_old_path=rollback_old_path,
        )


def paths_from_transaction_directory(
    base_path: str,
    transaction_path: str,
) -> UpdateTransactionPaths:
    return UpdateTransactionPaths(
        base_path=os.path.abspath(base_path),
        transaction_path=transaction_path,
        staged_new_path=os.path.join(transaction_path, STAGED_NEW_DIR),
        rollback_old_path=os.path.join(transaction_path, ROLLBACK_OLD_DIR),
    )


def cleanup_update_transaction(paths: UpdateTransactionPaths, logger: LoggerProtocol) -> bool:
    try:
        cleanup_path = os.path.join(
            paths.base_path,
            os.path.basename(paths.transaction_path).replace(
                TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX, 1
            ),
        )
        os.rename(paths.transaction_path, cleanup_path)
        fsync_directory(paths.base_path, strict=True)
        sync_remove_tree_no_symlinks(cleanup_path)
        fsync_directory(paths.base_path, strict=True)
        return True
    except TRANSACTION_DISPOSAL_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to clean up update transaction storage.",
            operation=OPERATION_CLEANUP_UPDATE_TRANSACTION,
            details={"transaction_path": paths.transaction_path},
            level="warning",
        )
        return False
