"""SoAI - Windows Docker Desktop Linux engine storage mapping [backend/core/system/docker_storage/windows_desktop_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ntpath
import re
from collections.abc import Callable
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.system.docker_storage.daemon import DockerDaemonIdentity
from core.system.docker_storage.location import (
    DOCKER_STORAGE_UNMAPPED,
    DockerStorageLocation,
    HostPathObservation,
    reject_docker_storage,
)
from core.system.docker_storage.native_storage import DOCKER_DESKTOP_OPERATING_SYSTEM
from core.system.docker_storage.windows_engine_owner import WindowsEngineOwner

__all__ = (
    "WindowsDesktopStorageHost",
    "map_windows_desktop_storage",
)

PROFILE_LIST_KEY = "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList"
LXSS_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Lxss"
SHELL_FOLDERS_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders"
_DESKTOP_USER_SID_PREFIXES = ("S-1-5-21-", "S-1-12-1-")
_ENGINE_IMAGE_PREFIX = "com.docker."
_ENGINE_IMAGE_NAMES = ("docker desktop.exe",)
_MAIN_DISTRIBUTION = "docker-desktop"
_LEGACY_DATA_DISTRIBUTION = "docker-desktop-data"
_SETTINGS_FILE_NAMES = ("settings-store.json", "settings.json")
_RELOCATION_SETTING_NAMES = ("CustomWslDistroDir", "customWslDistroDir")
_RELOCATED_SUBDIRECTORY = "DockerDesktopWSL"
_LOCAL_PIPE_PATTERN = r"npipe:////\./pipe/([A-Za-z0-9_.-]+)"
_LOCAL_DRIVE_PATH_PATTERN = r"[A-Za-z]:\\"
_USER_PROFILE_VARIABLE_PATTERN = r"%USERPROFILE%"
_EXTENDED_PATH_PREFIX = "\\\\?\\"


@dataclass(frozen=True, slots=True)
class WindowsDesktopStorageHost:
    resolve_engine_owner: Callable[[str], WindowsEngineOwner]
    read_registry_text: Callable[[str, str, str], str | None]
    list_registry_subkeys: Callable[[str, str], tuple[str, ...]]
    expand_system_text: Callable[[str], str]
    observe_path: Callable[[str], HostPathObservation | None]
    read_settings: Callable[[str], bytes]


def map_windows_desktop_storage(
    daemon: DockerDaemonIdentity, host: WindowsDesktopStorageHost
) -> DockerStorageLocation:
    if daemon.operating_system != DOCKER_DESKTOP_OPERATING_SYSTEM:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "linux_engine_not_docker_desktop")
    pipe = re.fullmatch(_LOCAL_PIPE_PATTERN, daemon.endpoint, re.IGNORECASE)
    if pipe is None:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "endpoint_not_local_pipe")
    owner = host.resolve_engine_owner(f"\\\\.\\pipe\\{pipe.group(1)}")
    if not owner.user_sid.startswith(_DESKTOP_USER_SID_PREFIXES):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "engine_owner_not_desktop_user")
    image_name = ntpath.basename(owner.image_path).casefold()
    if not image_name.startswith(_ENGINE_IMAGE_PREFIX) and image_name not in _ENGINE_IMAGE_NAMES:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "engine_owner_not_docker_desktop")
    profile_value = host.read_registry_text(
        "HKLM", f"{PROFILE_LIST_KEY}\\{owner.user_sid}", "ProfileImagePath"
    )
    if profile_value is None:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "engine_owner_profile_unregistered")
    profile = _local_path(host.expand_system_text(profile_value))
    distributions = _docker_distributions(host, owner.user_sid)
    main = distributions.get(_MAIN_DISTRIBUTION)
    if main is None:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "desktop_distribution_unregistered")
    wsl_root = ntpath.dirname(main)
    data_disk = _data_disk(host, wsl_root, distributions.get(_LEGACY_DATA_DISTRIBUTION))
    if ntpath.normcase(wsl_root) not in _configured_wsl_roots(host, owner.user_sid, profile):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "storage_configuration_mismatch")
    disk = _require_direct_path(host, data_disk, directory=False)
    directory = _require_direct_path(host, ntpath.dirname(data_disk), directory=True)
    return DockerStorageLocation(
        endpoint=daemon.endpoint,
        daemon_id=daemon.daemon_id,
        daemon_os_type=daemon.os_type,
        storage_type="desktop_virtual_disk",
        host_storage_path=directory.real_path,
        host_storage_identity=directory.identity,
        backing_image_path=disk.real_path,
        backing_image_identity=disk.identity,
    )


def _docker_distributions(host: WindowsDesktopStorageHost, user_sid: str) -> dict[str, str]:
    registry_key = f"{user_sid}\\{LXSS_KEY}"
    distributions: dict[str, str] = {}
    for subkey in host.list_registry_subkeys("HKU", registry_key):
        distribution_key = f"{registry_key}\\{subkey}"
        name = host.read_registry_text("HKU", distribution_key, "DistributionName")
        if name not in (_MAIN_DISTRIBUTION, _LEGACY_DATA_DISTRIBUTION):
            continue
        base_path = host.read_registry_text("HKU", distribution_key, "BasePath")
        if base_path is None or name in distributions:
            reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "desktop_distribution_ambiguous")
        distributions[name] = _local_path(base_path)
    return distributions


def _data_disk(host: WindowsDesktopStorageHost, wsl_root: str, legacy_root: str | None) -> str:
    candidates = [ntpath.join(wsl_root, "disk", "docker_data.vhdx")]
    if legacy_root is not None:
        if ntpath.normcase(ntpath.dirname(legacy_root)) != ntpath.normcase(wsl_root):
            reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "desktop_distribution_ambiguous")
        candidates.append(ntpath.join(legacy_root, "ext4.vhdx"))
    present = [path for path in candidates if host.observe_path(path) is not None]
    if not present:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "data_disk_missing")
    if len(present) > 1:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "data_disk_ambiguous")
    return present[0]


def _configured_wsl_roots(
    host: WindowsDesktopStorageHost, user_sid: str, profile: str
) -> frozenset[str]:
    roaming = _user_folder(host, user_sid, "AppData", profile, ("AppData", "Roaming"))
    relocation = _relocation_setting(host, ntpath.join(roaming, "Docker"))
    if relocation is None:
        local = _user_folder(host, user_sid, "Local AppData", profile, ("AppData", "Local"))
        return frozenset((ntpath.normcase(ntpath.join(local, "Docker", "wsl")),))
    root = _local_path(relocation)
    return frozenset(
        ntpath.normcase(path) for path in (root, ntpath.join(root, _RELOCATED_SUBDIRECTORY))
    )


def _relocation_setting(host: WindowsDesktopStorageHost, settings_directory: str) -> str | None:
    for file_name in _SETTINGS_FILE_NAMES:
        settings_path = ntpath.join(settings_directory, file_name)
        observation = host.observe_path(settings_path)
        if observation is None:
            continue
        if not observation.is_regular_file or observation.is_reparse_point:
            reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "settings_untrusted")
        try:
            settings = parse_json_dict(host.read_settings(settings_path), field="docker settings")
        except ValidationError:
            reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "settings_malformed")
        values = [settings[name] for name in _RELOCATION_SETTING_NAMES if name in settings]
        configured = [value for value in values if value not in (None, "")]
        if any(not isinstance(value, str) for value in configured) or len(set(configured)) > 1:
            reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "settings_malformed")
        relocation = configured[0] if configured else None
        return relocation if isinstance(relocation, str) else None
    return None


def _user_folder(
    host: WindowsDesktopStorageHost,
    user_sid: str,
    value_name: str,
    profile: str,
    default_parts: tuple[str, str],
) -> str:
    configured = host.read_registry_text("HKU", f"{user_sid}\\{SHELL_FOLDERS_KEY}", value_name)
    if configured is None:
        return ntpath.join(profile, *default_parts)
    expanded = re.sub(
        _USER_PROFILE_VARIABLE_PATTERN, lambda _match: profile, configured, flags=re.IGNORECASE
    )
    if "%" in expanded:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "user_folder_unresolvable")
    return _local_path(expanded)


def _local_path(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith(_EXTENDED_PATH_PREFIX):
        candidate = candidate[len(_EXTENDED_PATH_PREFIX) :]
    if re.match(_LOCAL_DRIVE_PATH_PATTERN, candidate) is None:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "path_not_local")
    return ntpath.normpath(candidate)


def _require_direct_path(
    host: WindowsDesktopStorageHost, path: str, *, directory: bool
) -> HostPathObservation:
    observation = host.observe_path(path)
    if observation is None:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "data_disk_missing")
    expected_type = observation.is_directory if directory else observation.is_regular_file
    if (
        not expected_type
        or observation.is_reparse_point
        or observation.is_remote
        or ntpath.normcase(observation.real_path) != ntpath.normcase(path)
    ):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "data_disk_unverifiable")
    return observation
