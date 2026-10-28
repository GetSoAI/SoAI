"""SoAI - Managed ripgrep binary bootstrap [backend/core/bootstrap/ripgrep_binary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import uuid

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.files import write_text_file_atomic
from core.bootstrap.launcher_config import is_offline_mode_enabled
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.managed_archive_extraction import detect_managed_asset_platform_id
from core.bootstrap.managed_asset_installation import install_managed_asset_archive
from core.bootstrap.managed_install_marker import read_managed_install_marker
from core.bootstrap.packaged_asset_paths import resolve_packaged_asset
from core.bootstrap.ripgrep_binary_assets import (
    RIPGREP_RELEASE,
    RIPGREP_RELEASE_DIR,
    RIPGREP_VERSION_LINE,
    RipgrepAsset,
    get_ripgrep_assets,
)
from core.bootstrap.runtime_directory_publication import (
    publish_runtime_directory,
    recover_runtime_directory_publication,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.windows_sharing_conflicts import remove_path_with_sharing_retry
from core.meta.paths import join_data_abs
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.system.native_runtime_probes import capture_native_probe, native_probe_budget
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("ensure_ripgrep_installed", "is_ripgrep_installed")


def _compute_state_dir(repo_root_path: str) -> str:
    return join_data_abs(repo_root_path, "state")


def _compute_install_base(repo_root_path: str) -> str:
    return os.path.join(
        _compute_state_dir(repo_root_path),
        "ripgrep",
        f"ripgrep-{RIPGREP_RELEASE_DIR}",
    )


def _compute_lock_path(repo_root_path: str) -> str:
    return os.path.join(
        _compute_state_dir(repo_root_path),
        "locks",
        "soai.ripgrep_binary.lock",
    )


def _detect_ripgrep_platform_id() -> str:
    assets = get_ripgrep_assets()
    return detect_managed_asset_platform_id(
        managed_asset="ripgrep",
        supported_platform_ids=assets.keys(),
    )


def _find_ripgrep_binary(extracted_root: str) -> str:
    candidates: list[str] = []
    for directory_path, _, filenames in os.walk(extracted_root):
        for filename in filenames:
            if filename.lower() in ("rg", "rg.exe"):
                candidates.append(os.path.join(directory_path, filename))
    if not candidates:
        raise StateError("Managed ripgrep install is missing an rg binary.")
    candidates.sort(key=lambda path: len(os.path.normpath(path).split(os.sep)))
    binary_path = os.path.abspath(candidates[0])
    _require_regular_binary(binary_path)
    return binary_path


def _ensure_executable(binary_path: str) -> None:
    if os.name == "nt":
        return
    current_mode = os.stat(binary_path).st_mode
    os.chmod(binary_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def is_ripgrep_installed(repo_root_path: str) -> bool:
    platform_id = _detect_ripgrep_platform_id()
    asset = get_ripgrep_assets()[platform_id]
    install_directory = os.path.join(_compute_install_base(repo_root_path), platform_id)
    installed = True
    try:
        _require_install_directory(
            install_directory,
            final_install_directory=install_directory,
            asset=asset,
            platform_id=platform_id,
        )
    except (OSError, StateError, ValueError):
        installed = False
    return installed


def ensure_ripgrep_installed(repo_root_path: str) -> str:
    platform_id = _detect_ripgrep_platform_id()
    asset = get_ripgrep_assets().get(platform_id)
    if asset is None:
        raise StateError(f"No managed ripgrep asset found for platform: {platform_id}")
    base_directory = _compute_install_base(repo_root_path)
    os.makedirs(base_directory, exist_ok=True)
    install_directory = os.path.join(base_directory, platform_id)

    def validate_install_directory(directory: str) -> None:
        _require_install_directory(
            directory,
            final_install_directory=install_directory,
            asset=asset,
            platform_id=platform_id,
        )

    with acquire_interprocess_lock(_compute_lock_path(repo_root_path), timeout_sec=1800.0):
        recover_runtime_directory_publication(install_directory, validate_install_directory)
        existing_binary_path: str | None = None
        try:
            validate_install_directory(install_directory)
            marker = _read_required_marker(install_directory)
            existing_binary_path = marker["rg_bin"]
            _ensure_executable(existing_binary_path)
        except (OSError, StateError, ValueError):
            existing_binary_path = None
        if existing_binary_path is not None:
            return existing_binary_path
        packaged_archive_path = resolve_packaged_asset(
            repo_root_path,
            selected_directory=("runtime-assets", "ripgrep", platform_id),
            filename=asset.filename,
            managed_asset="ripgrep",
        )
        if packaged_archive_path is None and is_offline_mode_enabled(repo_root_path):
            raise StateError(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled and the packaged ripgrep asset is absent. Install an official package containing this platform or disable SYSTEM.RUNTIME.STAY_OFFLINE in config.yaml."
            )
        staging_directory = os.path.join(
            base_directory,
            f".{platform_id}.staging.{os.getpid()}.{uuid.uuid4().hex}",
        )
        reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)
        try:
            extracted_root = install_managed_asset_archive(
                install_dir=staging_directory,
                managed_asset="ripgrep",
                download_url=asset.url,
                expected_sha256=asset.sha256,
                user_agent="SoAI/managed-ripgrep",
                archive_format=asset.archive_format,
                download_prefix="soai-rg-download-",
                max_download_bytes=32 * MIB_BYTES,
                reservation_provider=reservation_provider,
                packaged_archive_path=packaged_archive_path,
            )
            staged_binary = _find_ripgrep_binary(extracted_root)
            _ensure_executable(staged_binary)
            _require_ripgrep_version(staged_binary)
            binary_relative_path = os.path.relpath(staged_binary, staging_directory)
            final_binary_path = os.path.abspath(
                os.path.join(install_directory, binary_relative_path)
            )
            marker_payload = {
                "release": RIPGREP_RELEASE,
                "platform_id": platform_id,
                "archive_url": asset.url,
                "archive_sha256": asset.sha256,
                "rg_bin": final_binary_path,
            }
            write_text_file_atomic(
                os.path.join(staging_directory, "install.json"),
                f"{serialize_json_pretty_sorted_strict(marker_payload)}\n",
            )
            publish_runtime_directory(
                staging_directory,
                install_directory,
                validate_install_directory,
            )
        finally:
            if os.path.isdir(staging_directory) and not os.path.islink(staging_directory):
                remove_path_with_sharing_retry(staging_directory)
        marker = _read_required_marker(install_directory)
        return marker["rg_bin"]


def _read_required_marker(install_directory: str) -> dict[str, str]:
    marker = read_managed_install_marker(
        os.path.join(install_directory, "install.json"),
        field="managed ripgrep install marker",
    )
    if marker is None:
        raise StateError("Managed ripgrep install marker is missing or invalid.")
    return marker


def _require_install_directory(
    directory: str,
    *,
    final_install_directory: str,
    asset: RipgrepAsset,
    platform_id: str,
) -> None:
    marker = _read_required_marker(directory)
    if set(marker) != {
        "release",
        "platform_id",
        "archive_url",
        "archive_sha256",
        "rg_bin",
    }:
        raise StateError("Managed ripgrep install marker has unexpected fields.")
    if (
        marker["release"] != RIPGREP_RELEASE
        or marker["platform_id"] != platform_id
        or marker["archive_url"] != asset.url
        or marker["archive_sha256"] != asset.sha256
    ):
        raise StateError("Managed ripgrep install marker does not match its selected pin.")
    final_binary_path = os.path.abspath(marker["rg_bin"])
    final_directory = os.path.abspath(final_install_directory)
    try:
        relative_binary_path = os.path.relpath(final_binary_path, final_directory)
    except ValueError as exception:
        raise StateError("Managed ripgrep binary path is outside its installation.") from exception
    if relative_binary_path == ".." or relative_binary_path.startswith(f"..{os.sep}"):
        raise StateError("Managed ripgrep binary path is outside its installation.")
    binary_path = os.path.abspath(os.path.join(directory, relative_binary_path))
    _require_regular_binary(binary_path)
    _require_ripgrep_version(binary_path)


def _require_regular_binary(binary_path: str) -> None:
    try:
        status = os.lstat(binary_path)
    except OSError as exception:
        raise StateError("Managed ripgrep binary is missing.") from exception
    if (
        not stat.S_ISREG(status.st_mode)
        or stat.S_ISLNK(status.st_mode)
        or is_windows_reparse_point(status)
    ):
        raise StateError("Managed ripgrep binary path is unsafe.")


def _require_ripgrep_version(binary_path: str) -> None:
    result = capture_native_probe(
        [binary_path, "--version"],
        budget=native_probe_budget(CONTROL_TIMEOUT_SEC, roots=(binary_path,)),
        subject="The managed ripgrep version check",
    )
    first_line = result.stdout.splitlines()[0].strip() if result.stdout else ""
    if result.return_code != 0 or first_line != RIPGREP_VERSION_LINE:
        raise StateError("Managed ripgrep version validation failed.")
