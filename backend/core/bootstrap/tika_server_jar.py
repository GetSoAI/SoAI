"""SoAI - Managed Apache Tika distribution bootstrap [backend/core/bootstrap/tika_server_jar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

import httpx2

from core.bootstrap.disk_reservation_provider import create_bootstrap_disk_reservation_provider
from core.bootstrap.download_stream import download_http_binary_to_path
from core.bootstrap.files import compute_sha512
from core.bootstrap.launcher_config import is_offline_mode_enabled
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.managed_archive_extraction import extract_managed_asset_archive
from core.bootstrap.packaged_asset_paths import resolve_packaged_asset
from core.bootstrap.runtime_directory_publication import (
    publish_runtime_directory,
    recover_runtime_directory_publication,
)
from core.bootstrap.tika_distribution_integrity import (
    validate_tika_archive,
    validate_tika_runtime,
)
from core.bootstrap.tika_runtime_assets import (
    TIKA_DISTRIBUTION_NAME,
    TIKA_DISTRIBUTION_SHA512,
    TIKA_DISTRIBUTION_URL,
    TIKA_SERVER_CONFIG,
    TIKA_SERVER_CONFIG_NAME,
    TIKA_SERVER_JAR_NAME,
    TIKA_SERVER_VERSION,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import StorageManagerProtocol
from core.meta.paths import join_data_abs

__all__ = (
    "ensure_tika_server_jar_installed",
    "has_verified_packaged_tika_distribution",
    "is_tika_server_jar_installed",
)


def _compute_tika_dir(repo_root_path: str) -> str:
    return join_data_abs(repo_root_path, "state", "tika")


def _compute_install_dir(repo_root_path: str) -> str:
    return os.path.join(_compute_tika_dir(repo_root_path), TIKA_SERVER_VERSION)


def _compute_jar_path(repo_root_path: str) -> str:
    return os.path.join(_compute_install_dir(repo_root_path), "runtime", TIKA_SERVER_JAR_NAME)


def _resolve_packaged_paths(repo_root_path: str) -> tuple[str, str] | None:
    archive_path = resolve_packaged_asset(
        repo_root_path,
        selected_directory=("runtime-assets",),
        filename=TIKA_DISTRIBUTION_NAME,
        managed_asset="Apache Tika",
    )
    if archive_path is None:
        return None
    checksum_path = resolve_packaged_asset(
        repo_root_path,
        selected_directory=("runtime-assets",),
        filename=f"{TIKA_DISTRIBUTION_NAME}.sha512",
        managed_asset="Apache Tika",
    )
    if checksum_path is None:
        raise StateError("Packaged Apache Tika checksum is missing.")
    return archive_path, checksum_path


def is_tika_server_jar_installed(repo_root_path: str) -> bool:
    runtime_verified = True
    try:
        validate_tika_runtime(_compute_install_dir(repo_root_path))
    except (OSError, StateError, ValueError, zipfile.BadZipFile):
        runtime_verified = False
    return runtime_verified


def has_verified_packaged_tika_distribution(repo_root_path: str) -> bool:
    distribution_verified = False
    try:
        packaged_paths = _resolve_packaged_paths(repo_root_path)
        if packaged_paths is not None:
            validate_tika_archive(*packaged_paths)
            distribution_verified = True
    except (OSError, StateError, ValueError):
        distribution_verified = False
    return distribution_verified


def ensure_tika_server_jar_installed(repo_root_path: str) -> tuple[str, str]:
    lock_path = join_data_abs(repo_root_path, "state", "locks", "soai.tika_jar.lock")
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        install_directory = _compute_install_dir(repo_root_path)
        recover_runtime_directory_publication(install_directory, validate_tika_runtime)
        if is_tika_server_jar_installed(repo_root_path):
            return _installed_paths(repo_root_path)
        packaged_paths = _resolve_packaged_paths(repo_root_path)
        if packaged_paths is not None:
            validate_tika_archive(*packaged_paths)
        elif is_offline_mode_enabled(repo_root_path):
            raise StateError(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled but the Apache Tika distribution is missing or invalid. Run once online to bootstrap it, or disable SYSTEM.RUNTIME.STAY_OFFLINE in config.yaml."
            )
        tika_directory = _compute_tika_dir(repo_root_path)
        os.makedirs(tika_directory, exist_ok=True)
        reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)
        with tempfile.TemporaryDirectory(dir=tika_directory, prefix=".tika-install-") as staging:
            archive_path = os.path.join(staging, TIKA_DISTRIBUTION_NAME)
            checksum_path = f"{archive_path}.sha512"
            if packaged_paths is None:
                _download_distribution(archive_path, reservation_provider)
            else:
                _copy_packaged_distribution(packaged_paths[0], archive_path, reservation_provider)
            distribution_digest = (
                TIKA_DISTRIBUTION_SHA512 if packaged_paths is None else compute_sha512(archive_path)
            )
            _write_runtime_record(checksum_path, distribution_digest, reservation_provider)
            validate_tika_archive(archive_path, checksum_path)
            extract_managed_asset_archive(
                archive_path,
                extracted_root=os.path.join(staging, "runtime"),
                archive_format="zip",
                managed_asset="Apache Tika",
                reservation_provider=reservation_provider,
            )
            _write_runtime_record(
                os.path.join(staging, TIKA_SERVER_CONFIG_NAME),
                TIKA_SERVER_CONFIG,
                reservation_provider,
            )
            publish_runtime_directory(staging, install_directory, validate_tika_runtime)
        return _installed_paths(repo_root_path)


def _installed_paths(repo_root_path: str) -> tuple[str, str]:
    return (
        _compute_jar_path(repo_root_path),
        os.path.join(_compute_install_dir(repo_root_path), f"{TIKA_DISTRIBUTION_NAME}.sha512"),
    )


def _download_distribution(path: str, reservation_provider: StorageManagerProtocol) -> None:
    try:
        download_http_binary_to_path(
            TIKA_DISTRIBUTION_URL,
            target_path=path,
            user_agent="SoAI/managed-tika",
            timeout_sec=300.0,
            reservation_provider=reservation_provider,
            max_bytes=256 * MIB_BYTES,
            require_https_final_url=True,
        )
    except (OSError, httpx2.HTTPError) as exception:
        raise StateError("Failed to download the Apache Tika distribution.") from exception


def _copy_packaged_distribution(
    source: str, destination: str, reservation_provider: StorageManagerProtocol
) -> None:
    size = os.path.getsize(source)
    with reservation_provider.reserve_disk_space(
        path=destination,
        required_bytes=size,
        operation="core.bootstrap.tika_server_jar.copy_distribution",
        details={"archive_path": destination},
    ) as reservation:
        with reservation.claim_write_bytes(size) as claim:
            shutil.copyfile(source, destination)
            claim.commit()


def _write_runtime_record(
    path: str, content: str, reservation_provider: StorageManagerProtocol
) -> None:
    payload = content.encode("utf-8")
    with reservation_provider.reserve_disk_space(
        path=path,
        required_bytes=len(payload),
        operation="core.bootstrap.tika_server_jar.write_runtime_record",
        details={"record_path": path},
    ) as reservation:
        with reservation.claim_write_bytes(len(payload)) as claim:
            with open(path, "wb") as handle:
                handle.write(payload)
            claim.commit()
