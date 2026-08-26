"""SoAI - Managed ripgrep binary bootstrap [backend/core/bootstrap/ripgrep_binary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.launcher_config import is_offline_mode_enabled
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.managed_archive_extraction import (
    detect_managed_asset_platform_id,
)
from core.bootstrap.managed_asset_installation import install_managed_asset_archive
from core.bootstrap.managed_install_marker import read_managed_install_marker
from core.bootstrap.ripgrep_binary_assets import (
    RIPGREP_RELEASE,
    RIPGREP_RELEASE_DIR,
    get_ripgrep_assets,
)
from core.errors.exceptions import StateError
from core.meta.paths import join_data_abs
from core.serialization.json import serialize_json_pretty_sorted_strict

__all__ = (
    "ensure_ripgrep_installed",
    "is_ripgrep_installed",
)


def _compute_state_dir(repo_root_path: str) -> str:
    return join_data_abs(repo_root_path, "state")


def _compute_install_base(repo_root_path: str) -> str:
    return os.path.join(
        _compute_state_dir(repo_root_path),
        "ripgrep",
        f"ripgrep-{RIPGREP_RELEASE_DIR}",
    )


def _compute_lock_path(repo_root_path: str) -> str:
    return os.path.join(_compute_state_dir(repo_root_path), "locks", "soai.ripgrep_binary.lock")


def _detect_ripgrep_platform_id() -> str:
    assets = get_ripgrep_assets()
    return detect_managed_asset_platform_id(
        managed_asset="ripgrep",
        supported_platform_ids=assets.keys(),
    )


def _find_ripgrep_binary(extracted_root: str) -> str:
    candidates: list[str] = []
    for dirpath, _, filenames in os.walk(extracted_root):
        for filename in filenames:
            lowered = filename.lower()
            if lowered in ("rg", "rg.exe"):
                candidates.append(os.path.join(dirpath, filename))
    if not candidates:
        raise StateError("Managed ripgrep install is missing an rg binary.")
    candidates_sorted = sorted(
        candidates,
        key=lambda path: len(os.path.normpath(path).split(os.sep)),
    )
    rg_bin = os.path.abspath(candidates_sorted[0])
    if not os.path.isfile(rg_bin):
        raise StateError("Managed ripgrep binary path is invalid.")
    return rg_bin


def _ensure_executable(binary_path: str) -> None:
    if os.name == "nt":
        return
    current_mode = os.stat(binary_path).st_mode
    os.chmod(binary_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def is_ripgrep_installed(repo_root_path: str) -> bool:
    base = _compute_install_base(repo_root_path)
    platform_id = _detect_ripgrep_platform_id()
    install_dir = os.path.join(base, platform_id)
    marker = read_managed_install_marker(
        os.path.join(install_dir, "install.json"),
        field="managed ripgrep install marker",
    )
    if not marker:
        return False
    rg_bin = marker.get("rg_bin")
    if not isinstance(rg_bin, str) or not rg_bin:
        return False
    return os.path.isfile(rg_bin)


def ensure_ripgrep_installed(repo_root_path: str) -> str:
    base = _compute_install_base(repo_root_path)
    os.makedirs(base, exist_ok=True)
    platform_id = _detect_ripgrep_platform_id()
    asset = get_ripgrep_assets().get(platform_id)
    if asset is None:
        raise StateError(f"No managed ripgrep asset found for platform: {platform_id}")
    install_dir = os.path.join(base, platform_id)
    marker_path = os.path.join(install_dir, "install.json")
    lock_path = _compute_lock_path(repo_root_path)
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        marker = read_managed_install_marker(
            marker_path,
            field="managed ripgrep install marker",
        )
        if marker:
            rg_bin = marker.get("rg_bin")
            if isinstance(rg_bin, str) and rg_bin and os.path.isfile(rg_bin):
                _ensure_executable(rg_bin)
                return rg_bin

        if is_offline_mode_enabled(repo_root_path):
            raise StateError(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled but the managed ripgrep binary is missing or invalid. Run once online to bootstrap it, or disable SYSTEM.RUNTIME.STAY_OFFLINE in config.yaml.",
            )

        reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)
        extracted_root = install_managed_asset_archive(
            install_dir=install_dir,
            managed_asset="ripgrep",
            download_url=asset.url,
            expected_sha256=asset.sha256,
            user_agent="SoAI/managed-ripgrep",
            archive_format=asset.archive_format,
            download_prefix="soai-rg-download-",
            reservation_provider=reservation_provider,
        )

        rg_bin = _find_ripgrep_binary(extracted_root)
        _ensure_executable(rg_bin)
        payload = {
            "release": RIPGREP_RELEASE,
            "platform_id": platform_id,
            "archive_url": asset.url,
            "archive_sha256": asset.sha256,
            "rg_bin": rg_bin,
        }
        marker_text = f"{serialize_json_pretty_sorted_strict(payload)}\n"
        marker_bytes = marker_text.encode("utf-8")
        with reservation_provider.reserve_disk_space(
            path=marker_path,
            required_bytes=len(marker_bytes),
            operation="core.bootstrap.ripgrep_binary.write_marker",
            details={"marker_path": marker_path},
        ) as marker_reservation:
            with marker_reservation.claim_write_bytes(len(marker_bytes)) as claim:
                with open(marker_path, "w", encoding="utf-8", errors="strict") as handle:
                    handle.write(marker_text)
                claim.commit()
        return rg_bin
