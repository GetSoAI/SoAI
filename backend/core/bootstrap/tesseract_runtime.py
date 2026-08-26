"""SoAI - Managed Tesseract runtime bootstrap [backend/core/bootstrap/tesseract_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import uuid

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.files import compute_sha256, write_text_file_atomic
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.managed_archive_extraction import extract_managed_asset_archive
from core.bootstrap.managed_install_marker import read_managed_install_marker
from core.errors.exceptions import StateError
from core.filesystem.open_files import open_text
from core.meta.paths import join_data_abs
from core.platform.os import is_windows
from core.runtime.platform import get_runtime_platform
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.system.commands import run_argv_capture
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "TESSERACT_RELEASE",
    "TESSERACT_WINDOWS_BUILD",
    "TESSERACT_WINDOWS_VERSION_LINE",
    "ensure_tesseract_runtime_installed",
    "is_tesseract_runtime_installed",
)

TESSERACT_RELEASE = "5.5.3"
TESSERACT_WINDOWS_BUILD = "5.5.3.20260724"
TESSERACT_WINDOWS_VERSION_LINE = "tesseract v5.5.3.20260724"
_WINDOWS_ARCHIVE_NAME = "tesseract-5.5.3-windows-x64.zip"
_WINDOWS_MANIFEST_NAME = "tesseract-5.5.3-windows-x64.json"


def is_tesseract_runtime_installed(repo_root_path: str) -> bool:
    installed = True
    try:
        executable, data_directory = _resolve_candidate(repo_root_path)
        _require_valid_runtime(executable, data_directory)
    except (OSError, StateError, ValueError):
        installed = False
    return installed


def ensure_tesseract_runtime_installed(repo_root_path: str) -> tuple[str, str]:
    _clear_environment()
    if not is_windows():
        executable, data_directory = _resolve_posix_candidate(repo_root_path)
        _require_valid_runtime(executable, data_directory)
        _publish_environment(executable, data_directory)
        return executable, data_directory
    lock_path = join_data_abs(
        repo_root_path,
        "state",
        "locks",
        "soai.tesseract_runtime.lock",
    )
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        try:
            executable, data_directory = _resolve_windows_installed_candidate(repo_root_path)
            _require_valid_runtime(executable, data_directory)
        except (OSError, StateError, ValueError):
            executable, data_directory = _install_windows_runtime(repo_root_path)
        _publish_environment(executable, data_directory)
        return executable, data_directory


def _resolve_candidate(repo_root_path: str) -> tuple[str, str]:
    if is_windows():
        return _resolve_windows_installed_candidate(repo_root_path)
    return _resolve_posix_candidate(repo_root_path)


def _resolve_posix_candidate(repo_root_path: str) -> tuple[str, str]:
    environment_directory = os.path.join(repo_root_path, "soai_main_venv")
    executable = os.path.join(
        environment_directory,
        "bin",
        "tesseract",
    )
    data_directory = os.path.join(
        environment_directory,
        "share",
        "tessdata",
    )
    return os.path.abspath(executable), os.path.abspath(data_directory)


def _resolve_windows_installed_candidate(repo_root_path: str) -> tuple[str, str]:
    _require_windows_x64()
    install_directory = join_data_abs(
        repo_root_path,
        "state",
        "tesseract",
        f"tesseract-{TESSERACT_RELEASE}",
        "windows-x64",
    )
    marker_path = os.path.join(install_directory, "install.json")
    marker = read_managed_install_marker(marker_path, field="managed Tesseract install marker")
    manifest = _read_asset_manifest(
        os.path.join(repo_root_path, "runtime-assets", _WINDOWS_MANIFEST_NAME),
    )
    if (
        marker is None
        or marker.get("release") != TESSERACT_RELEASE
        or marker.get("archive_sha256") != manifest["archive_sha256"]
    ):
        raise StateError("Managed Tesseract install marker is missing or invalid.")
    return (
        os.path.join(install_directory, "tesseract.exe"),
        os.path.join(install_directory, "tessdata"),
    )


def _install_windows_runtime(repo_root_path: str) -> tuple[str, str]:
    _require_windows_x64()
    asset_directory = os.path.join(repo_root_path, "runtime-assets")
    archive_path = os.path.join(asset_directory, _WINDOWS_ARCHIVE_NAME)
    manifest_path = os.path.join(asset_directory, _WINDOWS_MANIFEST_NAME)
    manifest = _read_asset_manifest(manifest_path)
    expected_sha256 = manifest.get("archive_sha256", "")
    try:
        actual_sha256 = compute_sha256(archive_path)
    except OSError as exception:
        raise StateError("Managed Windows Tesseract archive is missing.") from exception
    if not expected_sha256 or actual_sha256 != expected_sha256:
        raise StateError("Managed Windows Tesseract archive digest is invalid.")
    install_directory = join_data_abs(
        repo_root_path,
        "state",
        "tesseract",
        f"tesseract-{TESSERACT_RELEASE}",
        "windows-x64",
    )
    parent_directory = os.path.dirname(install_directory)
    os.makedirs(parent_directory, exist_ok=True)
    staging_directory = os.path.join(
        parent_directory,
        f".windows-x64.staging.{os.getpid()}.{uuid.uuid4().hex}",
    )
    reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)
    try:
        os.makedirs(staging_directory, exist_ok=False)
        extract_managed_asset_archive(
            archive_path,
            extracted_root=staging_directory,
            archive_format="zip",
            managed_asset="Tesseract runtime",
            reservation_provider=reservation_provider,
        )
        executable = os.path.join(staging_directory, "tesseract.exe")
        data_directory = os.path.join(staging_directory, "tessdata")
        _require_valid_runtime(executable, data_directory)
        marker_payload = {
            "archive_sha256": expected_sha256,
            "release": TESSERACT_RELEASE,
        }
        write_text_file_atomic(
            os.path.join(staging_directory, "install.json"),
            f"{serialize_json_pretty_sorted_strict(marker_payload)}\n",
        )
        _replace_runtime_directory(staging_directory, install_directory)
    finally:
        if os.path.isdir(staging_directory):
            shutil.rmtree(staging_directory)
    return (
        os.path.join(install_directory, "tesseract.exe"),
        os.path.join(install_directory, "tessdata"),
    )


def _read_asset_manifest(path: str) -> dict[str, str]:
    try:
        with open_text(path, encoding="utf-8", errors="strict") as handle:
            parsed = parse_json_dict(handle.read(), field="Tesseract runtime asset manifest")
    except OSError as exception:
        raise StateError("Managed Windows Tesseract asset manifest is missing.") from exception
    values: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(value, str):
            raise StateError("Managed Windows Tesseract asset manifest is invalid.")
        values[key] = value
    if (
        values.get("release") != TESSERACT_RELEASE
        or values.get("architecture") != "x64"
        or values.get("version_line") != TESSERACT_WINDOWS_VERSION_LINE
        or not values.get("archive_sha256")
    ):
        raise StateError("Managed Windows Tesseract asset manifest is invalid.")
    return values


def _replace_runtime_directory(staging_directory: str, install_directory: str) -> None:
    backup_directory = f"{install_directory}.replaced.{uuid.uuid4().hex}"
    moved_existing = False
    try:
        if os.path.isdir(install_directory):
            os.replace(install_directory, backup_directory)
            moved_existing = True
        os.replace(staging_directory, install_directory)
    except OSError:
        if moved_existing and not os.path.exists(install_directory):
            os.replace(backup_directory, install_directory)
        raise
    finally:
        if os.path.isdir(backup_directory):
            shutil.rmtree(backup_directory)


def _require_windows_x64() -> None:
    if get_runtime_platform().platform_id != "windows-x64":
        raise StateError("Managed Tesseract supports only Windows x64 on Windows.")


def _require_valid_runtime(executable: str, data_directory: str) -> None:
    if not os.path.isfile(executable):
        raise StateError("Managed Tesseract executable is missing.")
    if not os.path.isfile(os.path.join(data_directory, "eng.traineddata")):
        raise StateError("Managed Tesseract English language data is missing.")
    environment = dict(os.environ)
    environment["TESSDATA_PREFIX"] = data_directory
    version_result = run_argv_capture(
        [executable, "--version"],
        timeout=CONTROL_TIMEOUT_SEC,
        env=environment,
    )
    first_line = version_result.stdout.splitlines()[0] if version_result.stdout else ""
    expected_version_line = (
        TESSERACT_WINDOWS_VERSION_LINE if is_windows() else f"tesseract {TESSERACT_RELEASE}"
    )
    if version_result.return_code != 0 or first_line.strip() != expected_version_line:
        raise StateError("Managed Tesseract version validation failed.")
    languages_result = run_argv_capture(
        [executable, "--list-langs"],
        timeout=CONTROL_TIMEOUT_SEC,
        env=environment,
    )
    languages = {line.strip() for line in languages_result.stdout.splitlines()}
    if languages_result.return_code != 0 or "eng" not in languages:
        raise StateError("Managed Tesseract English language validation failed.")


def _publish_environment(executable: str, data_directory: str) -> None:
    os.environ["SOAI_TESSERACT_CMD"] = executable
    os.environ["TESSDATA_PREFIX"] = data_directory


def _clear_environment() -> None:
    os.environ.pop("SOAI_TESSERACT_CMD", None)
    os.environ.pop("TESSDATA_PREFIX", None)
