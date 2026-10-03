"""SoAI - Managed Apache Tika server jar bootstrap [backend/core/bootstrap/tika_server_jar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import tempfile

import httpx2

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.download_stream import download_http_binary_to_path, download_http_text
from core.bootstrap.files import compute_sha512
from core.bootstrap.launcher_config import is_offline_mode_enabled
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.packaged_asset_paths import resolve_packaged_asset
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import StorageManagerProtocol
from core.meta.paths import join_data_abs
from core.network.errors import HTTPDownloadInsecureSchemeError

__all__ = (
    "TIKA_SERVER_JAR_SHA512",
    "TIKA_SERVER_VERSION",
    "ensure_tika_server_jar_installed",
    "is_tika_server_jar_installed",
)

TIKA_SERVER_VERSION = "3.3.2"
TIKA_SERVER_JAR_SHA512 = (
    "fb1f2fe5"
    "7ac458b0"
    "9d44d41d"
    "816f582e"
    "1d2fc934"
    "88acff62"
    "75caf414"
    "d8d5ef94"
    "e42166ed"
    "c0b488dc"
    "2fb6ef3a"
    "a21fab62"
    "b107c43b"
    "9060385f"
    "f6d675e3"
    "93c2c9e9"
)


def _tika_release_base_url() -> str:
    return f"https://archive.apache.org/dist/tika/{TIKA_SERVER_VERSION}"


def _tika_jar_url() -> str:
    return f"{_tika_release_base_url()}/tika-server-standard-{TIKA_SERVER_VERSION}.jar"


def _tika_jar_sha512_url() -> str:
    return f"{_tika_jar_url()}.sha512"


def _compute_state_dir(repo_root_path: str) -> str:
    return join_data_abs(repo_root_path, "state")


def _compute_tika_dir(repo_root_path: str) -> str:
    return os.path.join(_compute_state_dir(repo_root_path), "tika")


def _compute_lock_path(repo_root_path: str) -> str:
    return os.path.join(_compute_state_dir(repo_root_path), "locks", "soai.tika_jar.lock")


def _compute_jar_path(repo_root_path: str) -> str:
    return os.path.join(
        _compute_tika_dir(repo_root_path),
        f"tika-server-standard-{TIKA_SERVER_VERSION}.jar",
    )


def _resolve_packaged_paths(repo_root_path: str) -> tuple[str, str] | None:
    jar_name = f"tika-server-standard-{TIKA_SERVER_VERSION}.jar"
    jar_path = resolve_packaged_asset(
        repo_root_path,
        selected_directory=("runtime-assets",),
        filename=jar_name,
        managed_asset="Apache Tika",
    )
    if jar_path is None:
        return None
    checksum_path = resolve_packaged_asset(
        repo_root_path,
        selected_directory=("runtime-assets",),
        filename=f"{jar_name}.sha512",
        managed_asset="Apache Tika",
    )
    if checksum_path is None:
        raise StateError("Packaged Apache Tika checksum is missing.")
    return jar_path, checksum_path


def _download_text(url: str) -> str:
    try:
        return download_http_text(
            url,
            user_agent="SoAI/managed-tika",
            timeout_sec=120.0,
            max_bytes=MIB_BYTES,
        ).strip()
    except HTTPDownloadInsecureSchemeError as exception:
        raise StateError("Managed Tika download redirected to a non-HTTPS URL.") from exception
    except UnicodeDecodeError as exception:
        raise StateError("Failed to decode Tika checksum file as UTF-8.") from exception
    except httpx2.HTTPError as exception:
        raise StateError("Failed to download Apache Tika checksum file.") from exception


def _download_binary(
    url: str,
    *,
    target_path: str,
    reservation_provider: StorageManagerProtocol,
) -> None:
    try:
        download_http_binary_to_path(
            url,
            target_path=target_path,
            user_agent="SoAI/managed-tika",
            timeout_sec=300.0,
            reservation_provider=reservation_provider,
            max_bytes=256 * MIB_BYTES,
            require_https_final_url=True,
        )
    except (OSError, httpx2.HTTPError) as exception:
        raise StateError("Failed to download Apache Tika server jar.") from exception


def _read_expected_hash(hash_path: str, *, expected_len: int) -> str | None:
    content: str | None = None
    try:
        with open(hash_path, encoding="utf-8", errors="strict") as handle:
            content = handle.read() or ""
    except OSError:
        content = None
    if not content:
        return None
    if content != content.strip():
        return None
    token = content.split()[0].lower()
    if len(token) != expected_len or any(ch not in "0123456789abcdef" for ch in token):
        return None
    return token


def is_tika_server_jar_installed(repo_root_path: str) -> bool:
    jar_path = _compute_jar_path(repo_root_path)
    sha512_path = f"{jar_path}.sha512"
    if _jar_matches_expected_hash(jar_path, sha512_path):
        return True
    packaged_paths: tuple[str, str] | None = None
    packaged_asset_invalid = False
    try:
        packaged_paths = _resolve_packaged_paths(repo_root_path)
    except StateError:
        packaged_asset_invalid = True
    if packaged_asset_invalid:
        return False
    return packaged_paths is not None and _jar_matches_expected_hash(*packaged_paths)


def _jar_matches_expected_hash(jar_path: str, sha512_path: str) -> bool:
    if not os.path.isfile(jar_path) or not os.path.isfile(sha512_path):
        return False
    expected_sha512 = _read_expected_hash(sha512_path, expected_len=128)
    if expected_sha512 != TIKA_SERVER_JAR_SHA512:
        return False
    actual_sha512 = ""
    hash_computation_error: OSError | None = None
    try:
        actual_sha512 = compute_sha512(jar_path).lower()
    except OSError as exception:
        hash_computation_error = exception
    if hash_computation_error is not None:
        return False
    return actual_sha512 == TIKA_SERVER_JAR_SHA512


def ensure_tika_server_jar_installed(repo_root_path: str) -> tuple[str, str]:
    lock_path = _compute_lock_path(repo_root_path)
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        tika_dir = _compute_tika_dir(repo_root_path)
        jar_path = _compute_jar_path(repo_root_path)
        sha512_path = f"{jar_path}.sha512"
        if _jar_matches_expected_hash(jar_path, sha512_path):
            return (jar_path, sha512_path)
        packaged_paths = _resolve_packaged_paths(repo_root_path)
        if packaged_paths is not None:
            packaged_jar_path, packaged_sha512_path = packaged_paths
            if not _jar_matches_expected_hash(packaged_jar_path, packaged_sha512_path):
                raise StateError(
                    "Bundled Apache Tika server jar failed SHA-512 verification.",
                )
            return (packaged_jar_path, packaged_sha512_path)
        if is_offline_mode_enabled(repo_root_path):
            raise StateError(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled but the Apache Tika server jar is missing or invalid. Run once online to bootstrap it, or disable SYSTEM.RUNTIME.STAY_OFFLINE in config.yaml.",
            )
        os.makedirs(tika_dir, exist_ok=True)
        reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)
        checksum_tokens = _download_text(_tika_jar_sha512_url()).split()
        expected_sha512 = checksum_tokens[0].lower() if checksum_tokens else ""
        if len(expected_sha512) != 128 or any(
            ch not in "0123456789abcdef" for ch in expected_sha512
        ):
            raise StateError(
                "Invalid SHA-512 checksum payload received for Apache Tika server jar.",
            )
        if expected_sha512 != TIKA_SERVER_JAR_SHA512:
            raise StateError(
                "Published Apache Tika server jar checksum does not match the packaged release identity.",
            )
        staging_handle, staging_jar_path = tempfile.mkstemp(
            dir=tika_dir,
            prefix=f".tika-server-standard-{TIKA_SERVER_VERSION}-",
            suffix=".jar",
        )
        os.close(staging_handle)
        staging_sha512_path = f"{staging_jar_path}.sha512"
        try:
            _download_binary(
                _tika_jar_url(),
                target_path=staging_jar_path,
                reservation_provider=reservation_provider,
            )
            actual_sha512 = compute_sha512(staging_jar_path).lower()
            if actual_sha512 != expected_sha512:
                raise StateError("Apache Tika server jar checksum verification failed.")
            checksum_bytes = expected_sha512.encode("utf-8")
            with reservation_provider.reserve_disk_space(
                path=staging_sha512_path,
                required_bytes=len(checksum_bytes),
                operation="core.bootstrap.tika_server_jar.write_checksum",
                details={"sha512_path": staging_sha512_path},
            ) as checksum_reservation:
                with checksum_reservation.claim_write_bytes(len(checksum_bytes)) as claim:
                    with open(
                        staging_sha512_path,
                        "w",
                        encoding="utf-8",
                        errors="strict",
                    ) as handle:
                        handle.write(expected_sha512)
                    claim.commit()
            os.replace(staging_jar_path, jar_path)
            os.replace(staging_sha512_path, sha512_path)
        finally:
            if os.path.exists(staging_jar_path):
                os.unlink(staging_jar_path)
            if os.path.exists(staging_sha512_path):
                os.unlink(staging_sha512_path)
        return (jar_path, sha512_path)
