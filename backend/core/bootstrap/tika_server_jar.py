"""SoAI - Managed Apache Tika server jar bootstrap [backend/core/bootstrap/tika_server_jar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import tempfile

import httpx2

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.download_stream import download_http_binary_to_path
from core.bootstrap.files import compute_sha512
from core.bootstrap.launcher_config import is_offline_mode_enabled
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import StorageManagerProtocol
from core.meta.paths import join_data_abs
from core.network.outbound_http_profiles import build_service_outbound_headers

__all__ = (
    "ensure_tika_server_jar_installed",
    "is_tika_server_jar_installed",
)

_TIKA_VERSION = "3.3.2"


def _tika_release_base_url() -> str:
    return f"https://archive.apache.org/dist/tika/{_TIKA_VERSION}"


def _tika_jar_url() -> str:
    return f"{_tika_release_base_url()}/tika-server-standard-{_TIKA_VERSION}.jar"


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
        f"tika-server-standard-{_TIKA_VERSION}.jar",
    )


def _download_text(url: str) -> str:
    try:
        response = httpx2.get(
            url,
            headers=build_service_outbound_headers(user_agent="SoAI/managed-tika"),
            follow_redirects=True,
            timeout=120.0,
        )
    except httpx2.HTTPError as exception:
        raise StateError("Failed to download Apache Tika checksum file.") from exception
    try:
        final_url = str(response.url)
        if final_url and not final_url.startswith("https://"):
            raise StateError("Managed Tika download redirected to a non-HTTPS URL.")
        response.raise_for_status()
        payload = response.content
        decoded = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise StateError("Failed to decode Tika checksum file as UTF-8.") from exception
    except httpx2.HTTPError as exception:
        raise StateError("Failed to download Apache Tika checksum file.") from exception
    finally:
        response.close()
    return decoded.strip()


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
    if not os.path.isfile(jar_path) or not os.path.isfile(sha512_path):
        return False
    expected_sha512 = _read_expected_hash(sha512_path, expected_len=128)
    if expected_sha512 is None:
        return False
    actual_sha512 = ""
    try:
        actual_sha512 = compute_sha512(jar_path).lower()
    except OSError:
        actual_sha512 = ""
    return actual_sha512 == expected_sha512


def ensure_tika_server_jar_installed(repo_root_path: str) -> tuple[str, str]:
    lock_path = _compute_lock_path(repo_root_path)
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        tika_dir = _compute_tika_dir(repo_root_path)
        jar_path = _compute_jar_path(repo_root_path)
        sha512_path = f"{jar_path}.sha512"
        if is_tika_server_jar_installed(repo_root_path):
            return (jar_path, sha512_path)
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
        staging_handle, staging_jar_path = tempfile.mkstemp(
            dir=tika_dir,
            prefix=f".tika-server-standard-{_TIKA_VERSION}-",
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
