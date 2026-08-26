"""SoAI - Managed Java runtime bootstrap [backend/core/bootstrap/java_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.java_runtime_archive import find_java_binary
from core.bootstrap.java_runtime_assets import (
    JAVA_RUNTIME_RELEASE,
    JAVA_RUNTIME_RELEASE_DIR,
    get_java_runtime_assets,
)
from core.bootstrap.launcher_config import is_offline_mode_enabled
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.managed_archive_extraction import (
    detect_managed_asset_platform_id,
)
from core.bootstrap.managed_asset_installation import install_managed_asset_archive
from core.bootstrap.managed_install_marker import read_managed_install_marker
from core.errors.exceptions import StateError
from core.meta.paths import join_data_abs
from core.serialization.json import serialize_json_pretty_sorted_strict

__all__ = (
    "ensure_java_runtime_installed",
    "is_java_runtime_installed",
)


def _compute_state_dir(repo_root_path: str) -> str:
    return join_data_abs(repo_root_path, "state")


def _compute_install_base(repo_root_path: str) -> str:
    install_name = f"microsoft-openjdk-{JAVA_RUNTIME_RELEASE_DIR}"
    return os.path.join(_compute_state_dir(repo_root_path), "java", install_name)


def _compute_lock_path(repo_root_path: str) -> str:
    return os.path.join(_compute_state_dir(repo_root_path), "locks", "soai.java_runtime.lock")


def _detect_java_platform_id() -> str:
    assets = get_java_runtime_assets()
    return detect_managed_asset_platform_id(
        managed_asset="Java runtime",
        supported_platform_ids=assets.keys(),
    )


def is_java_runtime_installed(repo_root_path: str) -> bool:
    base = _compute_install_base(repo_root_path)
    platform_id = _detect_java_platform_id()
    install_dir = os.path.join(base, platform_id)
    marker_path = os.path.join(install_dir, "install.json")
    marker = read_managed_install_marker(marker_path, field="managed Java runtime install marker")
    if not marker:
        return False
    java_bin = marker.get("java_bin")
    if not isinstance(java_bin, str) or not java_bin:
        return False
    return os.path.isfile(java_bin)


def ensure_java_runtime_installed(repo_root_path: str) -> tuple[str, str]:
    base = _compute_install_base(repo_root_path)
    os.makedirs(base, exist_ok=True)
    platform_id = _detect_java_platform_id()
    asset = get_java_runtime_assets().get(platform_id)
    if asset is None:
        raise StateError(f"No managed Java runtime asset found for platform: {platform_id}")
    install_dir = os.path.join(base, platform_id)
    marker_path = os.path.join(install_dir, "install.json")
    lock_path = _compute_lock_path(repo_root_path)
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        marker = read_managed_install_marker(
            marker_path,
            field="managed Java runtime install marker",
        )
        if marker:
            java_bin = marker.get("java_bin")
            java_home = marker.get("java_home")
            if not isinstance(java_bin, str) or not java_bin:
                java_bin = None
            if not isinstance(java_home, str) or not java_home:
                java_home = None
            if isinstance(java_bin, str) and not os.path.isfile(java_bin):
                java_bin = None
            if isinstance(java_home, str) and not os.path.isdir(java_home):
                java_home = None
            if isinstance(java_bin, str) and isinstance(java_home, str):
                return (java_home, java_bin)

        if is_offline_mode_enabled(repo_root_path):
            raise StateError(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled but the managed Java runtime is missing or invalid. Run once online to bootstrap it, or disable SYSTEM.RUNTIME.STAY_OFFLINE in config.yaml.",
            )

        reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)

        extracted_root = install_managed_asset_archive(
            install_dir=install_dir,
            managed_asset="Java runtime",
            download_url=asset.url,
            expected_sha256=asset.sha256,
            user_agent="SoAI/managed-java",
            archive_format=asset.archive_format,
            reservation_provider=reservation_provider,
        )

        java_bin = find_java_binary(extracted_root)
        java_home = os.path.abspath(os.path.dirname(os.path.dirname(java_bin)))
        payload = {
            "provider": "microsoft-openjdk",
            "release": JAVA_RUNTIME_RELEASE,
            "platform_id": platform_id,
            "archive_url": asset.url,
            "archive_sha256": asset.sha256,
            "java_home": java_home,
            "java_bin": java_bin,
        }
        marker_text = f"{serialize_json_pretty_sorted_strict(payload)}\n"
        marker_bytes = marker_text.encode("utf-8")
        with reservation_provider.reserve_disk_space(
            path=marker_path,
            required_bytes=len(marker_bytes),
            operation="core.bootstrap.java_runtime.write_marker",
            details={"marker_path": marker_path},
        ) as marker_reservation:
            with marker_reservation.claim_write_bytes(len(marker_bytes)) as claim:
                with open(marker_path, "w", encoding="utf-8", errors="strict") as handle:
                    handle.write(marker_text)
                claim.commit()
        return (java_home, java_bin)
