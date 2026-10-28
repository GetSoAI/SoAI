"""SoAI - Managed Tesseract runtime bootstrap [backend/core/bootstrap/tesseract_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import uuid

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.files import compute_sha256, write_text_file_atomic
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.managed_archive_extraction import extract_managed_asset_archive
from core.bootstrap.managed_install_marker import read_managed_install_marker
from core.bootstrap.packaged_asset_paths import resolve_packaged_asset
from core.bootstrap.runtime_directory_publication import (
    publish_runtime_directory,
    recover_runtime_directory_publication,
)
from core.errors.exceptions import StateError
from core.filesystem.open_files import open_text
from core.filesystem.windows_sharing_conflicts import remove_path_with_sharing_retry
from core.media.tesseract_data import require_complete_tesseract_data, require_tesseract_model
from core.meta.paths import join_data_abs
from core.platform.os import is_windows
from core.runtime.platform import get_runtime_platform
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.system.native_runtime_probes import capture_native_probe, native_probe_budget
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "TESSERACT_RELEASE",
    "TESSERACT_WINDOWS_ARCHIVE_NAME",
    "TESSERACT_WINDOWS_BUILD",
    "TESSERACT_WINDOWS_MANIFEST_NAME",
    "TESSERACT_WINDOWS_VERSION_LINE",
    "ensure_tesseract_runtime_installed",
)

TESSERACT_RELEASE = "5.5.3"
TESSERACT_WINDOWS_BUILD = "5.5.3.20260724"
TESSERACT_WINDOWS_VERSION_LINE = "tesseract v5.5.3.20260724"
TESSERACT_WINDOWS_ARCHIVE_NAME = "tesseract-5.5.3-windows-x64.zip"
TESSERACT_WINDOWS_MANIFEST_NAME = "tesseract-5.5.3-windows-x64.json"


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
        install_directory = _windows_install_directory(repo_root_path)
        manifest = _read_asset_manifest(
            _resolve_windows_runtime_asset(
                repo_root_path,
                TESSERACT_WINDOWS_MANIFEST_NAME,
            )
        )
        recover_runtime_directory_publication(
            install_directory,
            lambda directory: _require_windows_install_directory(
                directory,
                manifest["archive_sha256"],
            ),
        )
        try:
            executable, data_directory = _resolve_windows_installed_candidate(repo_root_path)
            _require_valid_runtime(executable, data_directory)
        except (OSError, StateError, ValueError):
            executable, data_directory = _install_windows_runtime(repo_root_path)
        _publish_environment(executable, data_directory)
        return executable, data_directory


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
    install_directory = _windows_install_directory(repo_root_path)
    marker_path = os.path.join(install_directory, "install.json")
    marker = read_managed_install_marker(marker_path, field="managed Tesseract install marker")
    manifest = _read_asset_manifest(
        _resolve_windows_runtime_asset(
            repo_root_path,
            TESSERACT_WINDOWS_MANIFEST_NAME,
        ),
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
    archive_path = _resolve_windows_runtime_asset(
        repo_root_path,
        TESSERACT_WINDOWS_ARCHIVE_NAME,
    )
    manifest_path = _resolve_windows_runtime_asset(
        repo_root_path,
        TESSERACT_WINDOWS_MANIFEST_NAME,
    )
    manifest = _read_asset_manifest(manifest_path)
    expected_sha256 = manifest.get("archive_sha256", "")
    try:
        actual_sha256 = compute_sha256(archive_path)
    except OSError as exception:
        raise StateError("Managed Windows Tesseract archive is missing.") from exception
    if not expected_sha256 or actual_sha256 != expected_sha256:
        raise StateError("Managed Windows Tesseract archive digest is invalid.")
    install_directory = _windows_install_directory(repo_root_path)
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
        require_complete_tesseract_data(data_directory)
        marker_payload = {
            "archive_sha256": expected_sha256,
            "release": TESSERACT_RELEASE,
        }
        write_text_file_atomic(
            os.path.join(staging_directory, "install.json"),
            f"{serialize_json_pretty_sorted_strict(marker_payload)}\n",
        )
        publish_runtime_directory(
            staging_directory,
            install_directory,
            lambda directory: _require_windows_install_directory(
                directory,
                expected_sha256,
            ),
        )
    finally:
        if os.path.isdir(staging_directory):
            remove_path_with_sharing_retry(staging_directory)
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


def _resolve_windows_runtime_asset(repo_root_path: str, filename: str) -> str:
    path = resolve_packaged_asset(
        repo_root_path,
        selected_directory=("runtime-assets",),
        filename=filename,
        managed_asset="Windows Tesseract",
    )
    if path is None:
        raise StateError("Managed Windows Tesseract runtime asset is missing.")
    return path


def _windows_install_directory(repo_root_path: str) -> str:
    return join_data_abs(
        repo_root_path,
        "state",
        "tesseract",
        f"tesseract-{TESSERACT_RELEASE}",
        "windows-x64",
    )


def _require_windows_install_directory(
    install_directory: str,
    expected_archive_sha256: str,
) -> None:
    marker = read_managed_install_marker(
        os.path.join(install_directory, "install.json"),
        field="managed Tesseract install marker",
    )
    if marker != {
        "archive_sha256": expected_archive_sha256,
        "release": TESSERACT_RELEASE,
    }:
        raise StateError("Managed Tesseract install marker is missing or invalid.")
    executable = os.path.join(install_directory, "tesseract.exe")
    data_directory = os.path.join(install_directory, "tessdata")
    _require_valid_runtime(executable, data_directory)
    require_complete_tesseract_data(data_directory)


def _require_windows_x64() -> None:
    if get_runtime_platform().platform_id != "windows-x64":
        raise StateError("Managed Tesseract supports only Windows x64 on Windows.")


def _require_valid_runtime(executable: str, data_directory: str) -> None:
    if not os.path.isfile(executable):
        raise StateError("Managed Tesseract executable is missing.")
    require_tesseract_model(data_directory, "eng")
    environment = dict(os.environ)
    environment["TESSDATA_PREFIX"] = data_directory
    budget = native_probe_budget(
        CONTROL_TIMEOUT_SEC,
        roots=(os.path.dirname(executable),),
        excluded_names=("tessdata",),
        probe_count=2,
    )
    version_result = capture_native_probe(
        [executable, "--version"],
        budget=budget,
        subject="The managed Tesseract version check",
        env=environment,
    )
    first_line = version_result.stdout.splitlines()[0] if version_result.stdout else ""
    expected_version_line = (
        TESSERACT_WINDOWS_VERSION_LINE if is_windows() else f"tesseract {TESSERACT_RELEASE}"
    )
    if version_result.return_code != 0 or first_line.strip() != expected_version_line:
        raise StateError("Managed Tesseract version validation failed.")
    languages_result = capture_native_probe(
        [executable, "--list-langs"],
        budget=budget,
        subject="The managed Tesseract language check",
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
