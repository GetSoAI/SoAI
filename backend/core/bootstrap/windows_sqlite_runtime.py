"""SoAI - Windows managed SQLite runtime provisioning [backend/core/bootstrap/windows_sqlite_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
import zipfile

from core.archives.resource_limits import default_archive_resource_limits
from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.archives.zip_plan import build_validated_zip_plan
from core.archives.zip_plan_extraction import extract_validated_zip_members
from core.bootstrap.files import compute_sha3_256
from core.bootstrap.runtime_directories import RuntimeDirectoryEnvironment
from core.bootstrap.stage0_download import download_https_file_atomic
from core.errors.exceptions import StateError
from core.filesystem.open_files import open_binary
from core.system.commands import run_argv_capture
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

__all__ = ("ensure_windows_sqlite_runtime",)

WINDOWS_SQLITE_VERSION: tuple[int, int, int] = (3, 53, 3)
WINDOWS_SQLITE_MINIMUM_VERSION: tuple[int, int, int] = (3, 51, 3)
WINDOWS_SQLITE_ARCHIVE_URL = "https://www.sqlite.org/2026/sqlite-dll-win-x64-3530300.zip"
WINDOWS_SQLITE_ARCHIVE_SHA3_256_BYTES = (
    58,
    73,
    72,
    97,
    206,
    36,
    209,
    243,
    48,
    239,
    188,
    108,
    63,
    181,
    140,
    228,
    151,
    47,
    44,
    248,
    223,
    78,
    67,
    18,
    34,
    70,
    237,
    152,
    113,
    9,
    220,
    138,
)
WINDOWS_SQLITE_ARCHIVE_FILENAME = "sqlite-dll-win-x64-3530300.zip"
WINDOWS_SQLITE_MAX_DOWNLOAD_BYTES = 4_194_304


def _version_text(version: tuple[int, ...]) -> str:
    return ".".join(str(component) for component in version)


def _probe_sqlite_version(python_executable: str) -> tuple[int, ...]:
    result = run_argv_capture(
        [python_executable, "-c", "import sqlite3; print(sqlite3.sqlite_version)"],
        encoding="utf-8",
        errors="replace",
        timeout=INTERACTIVE_TIMEOUT_SEC,
    )
    output = result.stdout.strip()
    if result.return_code != 0 or not output:
        diagnostic = result.stderr.strip() or output or "no output"
        raise StateError(
            f"Managed Python SQLite runtime probe failed for '{python_executable}': {diagnostic}",
        )
    try:
        version = tuple(int(component) for component in output.split("."))
    except (TypeError, ValueError, OverflowError) as exception:
        raise StateError(
            f"Managed Python returned an invalid SQLite version: {output!r}.",
        ) from exception
    if len(version) < 3 or any(component < 0 for component in version):
        raise StateError(f"Managed Python returned an invalid SQLite version: {output!r}.")
    return version


def _archive_is_verified(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    expected_sha3_256 = bytes(WINDOWS_SQLITE_ARCHIVE_SHA3_256_BYTES).hex()
    return compute_sha3_256(path).lower() == expected_sha3_256


def _download_archive(cache_path: str) -> None:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    candidate_path = f"{cache_path}.download"
    try:
        download_https_file_atomic(
            WINDOWS_SQLITE_ARCHIVE_URL,
            target_path=candidate_path,
            user_agent="SoAI-Windows-SQLite-Bootstrap/1",
            timeout_sec=120.0,
            max_bytes=WINDOWS_SQLITE_MAX_DOWNLOAD_BYTES,
        )
        if not _archive_is_verified(candidate_path):
            raise StateError("Windows SQLite archive SHA3-256 verification failed.")
        os.replace(candidate_path, cache_path)
    finally:
        if os.path.exists(candidate_path):
            os.unlink(candidate_path)


def _is_same_directory(left_path: str, right_path: str) -> bool:
    normalized_left = os.path.normcase(os.path.realpath(left_path))
    normalized_right = os.path.normcase(os.path.realpath(right_path))
    return normalized_left == normalized_right


def _repo_root_is_lexical_ancestor(repo_root: str, base_prefix: str) -> bool:
    repo_drive = os.path.normcase(os.path.splitdrive(repo_root)[0])
    base_drive = os.path.normcase(os.path.splitdrive(base_prefix)[0])
    if repo_drive != base_drive:
        return False
    return os.path.commonpath((repo_root, base_prefix)) == repo_root


def _repo_root_owns_python_installation(repo_root: str, base_prefix: str) -> bool:
    if _repo_root_is_lexical_ancestor(repo_root, base_prefix):
        return True
    candidate = base_prefix
    while True:
        if _is_same_directory(candidate, repo_root):
            return True
        parent = os.path.dirname(candidate)
        if parent == candidate:
            return False
        candidate = parent


def _resolve_owned_sqlite_dll(repo_root_path: str) -> str:
    architecture = platform.machine().strip().lower()
    if architecture not in ("amd64", "x86_64"):
        raise StateError(
            f"Unsupported Windows architecture for managed SQLite: {architecture!r}.",
        )
    repo_root = os.path.normcase(os.path.abspath(repo_root_path))
    base_prefix = os.path.normcase(os.path.abspath(sys.base_prefix))
    if not _repo_root_owns_python_installation(repo_root, base_prefix):
        raise StateError(
            "Windows SQLite provisioning refuses to modify an external Python installation. Start SoAI through the supported Windows installer.",
        )
    sqlite_dll_path = os.path.join(base_prefix, "DLLs", "sqlite3.dll")
    if not os.path.isfile(sqlite_dll_path):
        raise StateError(
            f"SoAI-managed Python SQLite library is missing at '{sqlite_dll_path}'.",
        )
    return sqlite_dll_path


def _install_sqlite_dll(archive_path: str, sqlite_dll_path: str) -> None:
    target_directory = os.path.dirname(sqlite_dll_path)
    try:
        with open_binary(archive_path, mode="rb") as archive_handle:
            validate_zip_directory_budget(
                archive_handle,
                default_archive_resource_limits(),
            )
            with zipfile.ZipFile(archive_handle, mode="r") as archive:
                plan = build_validated_zip_plan(archive)
                matching_entries = tuple(
                    member
                    for member in plan.members
                    if not member.is_directory and member.destination_path == "sqlite3.dll"
                )
                if len(matching_entries) != 1:
                    raise StateError(
                        "Windows SQLite archive does not contain exactly one sqlite3.dll.",
                    )
                sqlite_member = matching_entries[0]
                if (
                    sqlite_member.file_size < 1
                    or sqlite_member.file_size > WINDOWS_SQLITE_MAX_DOWNLOAD_BYTES
                ):
                    raise StateError("Windows SQLite library size is invalid.")
                with tempfile.TemporaryDirectory(
                    prefix=".soai-sqlite-runtime.",
                    dir=target_directory,
                ) as extraction_directory:
                    extract_validated_zip_members(
                        archive,
                        (sqlite_member,),
                        extraction_directory,
                    )
                    extracted_dll_path = os.path.join(extraction_directory, "sqlite3.dll")
                    replacement_descriptor, replacement_path = tempfile.mkstemp(
                        prefix=".soai-sqlite3.",
                        suffix=".dll",
                        dir=target_directory,
                    )
                    try:
                        with os.fdopen(replacement_descriptor, "wb") as replacement_handle:
                            with open_binary(extracted_dll_path, mode="rb") as source_handle:
                                shutil.copyfileobj(source_handle, replacement_handle)
                            replacement_handle.flush()
                            os.fsync(replacement_handle.fileno())
                        os.replace(replacement_path, sqlite_dll_path)
                    finally:
                        if os.path.exists(replacement_path):
                            os.unlink(replacement_path)
    except (OSError, zipfile.BadZipFile) as exception:
        raise StateError("Windows SQLite runtime installation failed.") from exception


def ensure_windows_sqlite_runtime(
    repo_root_path: str,
    runtime_directories: RuntimeDirectoryEnvironment,
    *,
    python_executable: str,
    offline_mode: bool,
) -> None:
    installed_version = _probe_sqlite_version(python_executable)
    if installed_version >= WINDOWS_SQLITE_MINIMUM_VERSION:
        return
    sqlite_dll_path = _resolve_owned_sqlite_dll(repo_root_path)
    cache_directory = os.path.join(
        runtime_directories.state_path,
        "managed_runtime",
        "sqlite",
    )
    archive_path = os.path.join(cache_directory, WINDOWS_SQLITE_ARCHIVE_FILENAME)
    if not _archive_is_verified(archive_path):
        if offline_mode:
            installed_text = _version_text(installed_version)
            minimum_text = _version_text(WINDOWS_SQLITE_MINIMUM_VERSION)
            raise StateError(
                f"SYSTEM.RUNTIME.STAY_OFFLINE is enabled but Windows SQLite {installed_text} is unsafe. SQLite {minimum_text} or newer is required; run install-deps once online.",
            )
        _download_archive(archive_path)
    _install_sqlite_dll(archive_path, sqlite_dll_path)
    provisioned_version = _probe_sqlite_version(python_executable)
    if provisioned_version != WINDOWS_SQLITE_VERSION:
        expected_text = _version_text(WINDOWS_SQLITE_VERSION)
        actual_text = _version_text(provisioned_version)
        raise StateError(
            f"Windows SQLite provisioning expected {expected_text}, but managed Python loaded {actual_text}.",
        )
