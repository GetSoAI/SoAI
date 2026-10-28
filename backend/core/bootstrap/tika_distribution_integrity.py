"""SoAI - Complete Apache Tika runtime integrity [backend/core/bootstrap/tika_distribution_integrity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
import zipfile
from functools import partial

from core.bootstrap.files import BOOTSTRAP_FILE_HASH_CHUNK_BYTES, compute_sha512
from core.bootstrap.tika_runtime_assets import (
    TIKA_BUNDLED_DISTRIBUTION_SHA512,
    TIKA_DISTRIBUTION_NAME,
    TIKA_DISTRIBUTION_SHA512,
    TIKA_SERVER_CONFIG,
    TIKA_SERVER_CONFIG_NAME,
    TIKA_SERVER_JAR_NAME,
)
from core.errors.exceptions import StateError
from core.files.path_policy import safe_join_relative_under_base
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = ("validate_tika_archive", "validate_tika_runtime")


def validate_tika_archive(archive_path: str, checksum_path: str) -> None:
    for path in (archive_path, checksum_path):
        _require_plain_file(path)
    with open(checksum_path, encoding="ascii", errors="strict") as handle:
        expected_digest = handle.read(129)
        if expected_digest not in (TIKA_DISTRIBUTION_SHA512, TIKA_BUNDLED_DISTRIBUTION_SHA512):
            raise StateError("Apache Tika distribution checksum does not match its release pin.")
    if compute_sha512(archive_path) != expected_digest:
        raise StateError("Apache Tika distribution failed SHA-512 verification.")


def validate_tika_runtime(install_directory: str) -> None:
    _require_plain_directory(install_directory)
    archive_path = os.path.join(install_directory, TIKA_DISTRIBUTION_NAME)
    validate_tika_archive(archive_path, f"{archive_path}.sha512")
    configuration_path = os.path.join(install_directory, TIKA_SERVER_CONFIG_NAME)
    _require_plain_file(configuration_path)
    with open(configuration_path, encoding="utf-8", errors="strict") as handle:
        if handle.read(len(TIKA_SERVER_CONFIG) + 1) != TIKA_SERVER_CONFIG:
            raise StateError("Apache Tika server configuration is invalid.")
    runtime_directory = os.path.join(install_directory, "runtime")
    _require_plain_directory(runtime_directory)
    expected_files: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            if member.filename in expected_files:
                raise StateError("Apache Tika distribution contains duplicate files.")
            expected_files.add(member.filename)
            path = safe_join_relative_under_base(
                base_path=runtime_directory,
                relative_path=member.filename,
                description="Apache Tika distribution member",
                error_cls=StateError,
            )
            _require_plain_file(path)
            digest = hashlib.sha512()
            with archive.open(member) as handle:
                for chunk in iter(partial(handle.read, BOOTSTRAP_FILE_HASH_CHUNK_BYTES), b""):
                    digest.update(chunk)
            if compute_sha512(path) != digest.hexdigest():
                raise StateError("An Apache Tika runtime file failed integrity verification.")
    actual_files: set[str] = set()
    for directory, directories, filenames in os.walk(runtime_directory):
        for name in directories:
            path = os.path.join(directory, name)
            status = os.lstat(path)
            if stat.S_ISLNK(status.st_mode) or is_windows_reparse_point(status):
                raise StateError("Apache Tika runtime contains an unsafe directory.")
        for name in filenames:
            actual_files.add(
                os.path.relpath(os.path.join(directory, name), runtime_directory).replace(
                    os.sep, "/"
                )
            )
    if actual_files != expected_files or TIKA_SERVER_JAR_NAME not in expected_files:
        raise StateError("Apache Tika runtime file inventory is incomplete or unexpected.")
    if not any(name.startswith("lib/") and name.endswith(".jar") for name in expected_files):
        raise StateError("Apache Tika runtime dependencies are missing.")
    if not {"LICENSE", "NOTICE"}.issubset(expected_files):
        raise StateError("Apache Tika runtime legal materials are missing.")


def _require_plain_file(path: str) -> None:
    status = os.lstat(path)
    if not stat.S_ISREG(status.st_mode) or is_windows_reparse_point(status):
        raise StateError("Apache Tika runtime contains an unsafe file.")


def _require_plain_directory(path: str) -> None:
    status = os.lstat(path)
    if not stat.S_ISDIR(status.st_mode) or is_windows_reparse_point(status):
        raise StateError("Apache Tika runtime contains an unsafe directory.")
