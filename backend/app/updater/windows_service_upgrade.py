"""SoAI - Windows service identity upgrade for saved paths and launcher state [backend/app/updater/windows_service_upgrade.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from copy import deepcopy
from typing import TYPE_CHECKING

from app.config.schema_disk_reconciliation import ConfigPayloadTransformResult
from core.config.dotted_key_access import get_nested_config_value
from core.config.dotted_key_mutation import set_nested_config_value
from core.config.layout import (
    BASE_DOTTED_KEYS,
    BASE_PATH_KEY,
    DEFAULT_SYSTEM_DATA_PATH,
    STATE_DOTTED_KEYS,
)
from core.config.path_resolution import (
    ConfigPathResolutionError,
    iter_config_path_settings,
    resolve_path,
)
from core.files.windows_readonly_deletion import remove_tree_with_readonly_support
from core.filesystem.atomic_binary_writes import atomic_write_binary_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.meta.paths import join_data_abs
from core.security.tls_policy import (
    resolve_account_auto_tls_certificate_paths,
    resolve_auto_tls_certificate_paths,
)

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict
    from core.logging.protocols import LoggerProtocol

__all__ = ("migrate_windows_service_state", "upgrade_windows_service_paths")

_SYSTEM_DATA_KEY = "SYSTEM.PATHS.SYSTEM_DATA"
_LAUNCHER_APPEARANCE_FILE = "launcher-appearance.txt"
_SHARED_LAUNCHER_STATE_DIRECTORIES = ("launcher-webview2", "update-progress")
_CERTIFICATE_MAXIMUM_BYTES = 1024 * 1024
_CERTIFICATE_MOVED_MESSAGE = "Moved the HTTPS certificate into %s so the SoAI service keeps the identity that browsers and paired devices trust."
_SHARED_STATE_WARNING = "Shared launcher state could not be removed from %s: %s. Close every SoAI window, then run Setup again to remove it."


def _depends_on_identity(value: str) -> bool:
    return os.path.expanduser(os.path.expandvars(value)) != value


def _resolve_for_installing_identity(value: str, relative_root: str) -> str | None:
    try:
        return resolve_path(value, relative_root)
    except ConfigPathResolutionError:
        return None


def upgrade_windows_service_paths(
    payload: ConfigDict, *, base_path: str
) -> ConfigPayloadTransformResult:
    upgraded_payload = deepcopy(payload)
    changed_paths: list[str] = []
    for root_key in (BASE_PATH_KEY, _SYSTEM_DATA_KEY):
        value = get_nested_config_value(upgraded_payload, root_key)
        if isinstance(value, str) and _depends_on_identity(value):
            resolved_root = _resolve_for_installing_identity(value, base_path)
            if resolved_root is not None:
                set_nested_config_value(upgraded_payload, root_key, resolved_root)
                changed_paths.append(root_key)
    configured_system_data = get_nested_config_value(upgraded_payload, _SYSTEM_DATA_KEY)
    system_data_path = _resolve_for_installing_identity(
        (
            configured_system_data
            if isinstance(configured_system_data, str) and configured_system_data.strip()
            else DEFAULT_SYSTEM_DATA_PATH
        ),
        base_path,
    )
    for setting in iter_config_path_settings(
        upgraded_payload,
        state_dotted_keys=STATE_DOTTED_KEYS,
        base_dotted_keys=BASE_DOTTED_KEYS,
    ):
        if setting.dotted_key in (BASE_PATH_KEY, _SYSTEM_DATA_KEY) or not _depends_on_identity(
            setting.value
        ):
            continue
        relative_root = system_data_path if setting.relative_to_system_data else base_path
        if relative_root is None:
            continue
        resolved = _resolve_for_installing_identity(setting.value, relative_root)
        if resolved is not None:
            setting.parent[setting.key] = resolved
            changed_paths.append(setting.dotted_key)
    return ConfigPayloadTransformResult(
        data=upgraded_payload,
        changed_paths=tuple(sorted(changed_paths)),
    )


def _remove_shared_launcher_state(path: str) -> None:
    if os.path.islink(path):
        os.unlink(path)
        return
    if os.path.isjunction(path):
        os.rmdir(path)
        return
    if os.path.isdir(path):
        remove_tree_with_readonly_support(path)
        return
    os.remove(path)


def _carry_auto_tls_certificate(base_path: str, logger: LoggerProtocol) -> None:
    installation_paths = resolve_auto_tls_certificate_paths(base_path)
    account_paths = resolve_account_auto_tls_certificate_paths()
    if any(os.path.lexists(path) for path in installation_paths) or not all(
        os.path.isfile(path) and not os.path.islink(path) for path in account_paths
    ):
        return
    contents = [
        read_regular_file_no_symlink(path, max_bytes=_CERTIFICATE_MAXIMUM_BYTES)
        for path in account_paths
    ]
    os.makedirs(os.path.dirname(installation_paths[0]), mode=0o700, exist_ok=True)
    for path, content in zip(installation_paths, contents, strict=True):
        atomic_write_binary_content(path, content, file_mode=0o600, fsync_parent_directory=True)
    logger.info(_CERTIFICATE_MOVED_MESSAGE, os.path.dirname(installation_paths[0]))


def migrate_windows_service_state(base_path: str, logger: LoggerProtocol) -> None:
    _carry_auto_tls_certificate(base_path, logger)
    state_directory = join_data_abs(base_path, "state")
    legacy_appearance = os.path.join(state_directory, _LAUNCHER_APPEARANCE_FILE)
    local_application_data = os.environ.get("LOCALAPPDATA", "")
    if (
        os.path.isfile(legacy_appearance)
        and not os.path.islink(legacy_appearance)
        and os.path.isabs(local_application_data)
    ):
        user_state_directory = os.path.join(local_application_data, "SoAI")
        user_appearance = os.path.join(user_state_directory, _LAUNCHER_APPEARANCE_FILE)
        if not os.path.lexists(user_appearance):
            os.makedirs(user_state_directory, exist_ok=True)
            shutil.copyfile(legacy_appearance, user_appearance)
        os.remove(legacy_appearance)
        logger.info("Moved the launcher appearance to %s.", user_appearance)
    for name in _SHARED_LAUNCHER_STATE_DIRECTORIES:
        shared_state = os.path.join(state_directory, name)
        if not os.path.lexists(shared_state):
            continue
        try:
            _remove_shared_launcher_state(shared_state)
        except OSError as exception:
            logger.warning(_SHARED_STATE_WARNING, shared_state, str(exception))
            continue
        logger.info("Removed shared launcher state from %s.", shared_state)
