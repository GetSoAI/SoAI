"""SoAI - Managed install payload copy operations [backend/core/bootstrap/install_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.bootstrap.install_filesystem import unlink_if_exists
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_value
from core.timing.formatting import utc_now_log_format
from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "INSTALL_MANIFEST_FILENAME",
    "MANAGED_DOCUMENT_ENTRIES",
    "MANAGED_ROOT_ENTRIES",
    "managed_root_entries",
    "validate_existing_install_edition",
    "write_install_manifest",
)

INSTALL_MANIFEST_FILENAME = ".soai_install_manifest.json"

MANAGED_DOCUMENT_ENTRIES: tuple[str, ...] = (
    "CHANGE-DATES.md",
    "COMMERCIAL-LICENSING-AVAILABILITY.md",
    "COMMERCIAL-LICENSE.md",
    "COMMERCIAL-SUPPORT-TERMS.md",
    "LICENSE.md",
    "README.md",
    "NOTICE",
    "LICENSING.md",
    "PRIVACY.md",
    "ORGANIZATION-EVALUATION-TERMS.md",
    "DOCUMENTATION.md",
    "SECURITY.md",
    "RELEASE_NOTES.md",
    "requirements.txt",
)
MANAGED_ROOT_ENTRIES: tuple[str, ...] = (
    "backend",
    "frontend",
    "plugins",
    "licenses",
    "docs",
    "VERSION",
    "release-info-v1.json",
    *MANAGED_DOCUMENT_ENTRIES,
    "install-soai-macos.command",
    "install-soai-windows.ps1",
    "install-soai-linux.sh",
    "soai.sh",
    "soai.command",
    "soai.exe",
    "soai-app.ico",
    "Microsoft.Web.WebView2.Core.dll",
    "Microsoft.Web.WebView2.WinForms.dll",
    "WebView2Loader.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "python",
    "runtime-assets",
    "installer-support",
    "install-soai-from-release.sh",
    "install-soai-from-release.command",
    "install-soai-from-release.bat",
    "uninstall-soai-linux.sh",
)


def managed_root_entries(edition: str) -> tuple[str, ...]:
    if edition == "soai-core":
        return MANAGED_ROOT_ENTRIES
    if edition == "soai-os":
        return (*MANAGED_ROOT_ENTRIES, "soai_os")
    raise ValueError("Edition must be soai-core or soai-os.")


def validate_existing_install_edition(target: str, edition: str) -> None:
    manifest_path = os.path.join(target, INSTALL_MANIFEST_FILENAME)
    if not os.path.exists(manifest_path):
        if os.path.isdir(os.path.join(target, "soai_os")) and edition != "soai-os":
            raise ValidationError("Existing SoAI OS target does not match update edition.")
        return
    payload = parse_json_value(
        read_regular_file_no_symlink(manifest_path, max_bytes=64 * 1024),
        field="existing SoAI install manifest",
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("product") != "SoAI"
        or payload.get("edition") not in {"soai-core", "soai-os"}
    ):
        raise ValidationError("Existing SoAI install manifest is invalid.")
    if payload["edition"] != edition:
        raise ValidationError("Existing SoAI install edition does not match update edition.")


def write_install_manifest(
    target: str,
    source: str,
    *,
    reservation_provider: StorageManagerProtocol,
    edition: str,
    product_version: str,
    core_version: str,
) -> None:
    manifest_path = os.path.join(target, INSTALL_MANIFEST_FILENAME)
    payload: dict[str, JSONValue] = {
        "schema_version": 1,
        "edition": edition,
        "product": "SoAI",
        "version": product_version,
        "core_version": core_version,
        "installed_at": utc_now_log_format(),
        "source": source,
        "target": target,
    }
    manifest_text = f"{serialize_json_pretty_sorted_strict(payload, ensure_ascii=False)}\n"
    manifest_bytes = manifest_text.encode("utf-8")
    with (
        reservation_provider.reserve_disk_space(
            path=manifest_path,
            required_bytes=len(manifest_bytes),
            operation="core.bootstrap.install_payload.write_manifest",
            details={"manifest_path": manifest_path},
        ) as reservation,
        reservation.claim_write_bytes(len(manifest_bytes)) as claim,
    ):
        atomic_write_text_content(
            manifest_path,
            manifest_text,
            encoding="utf-8",
            errors="strict",
            fsync=True,
            fsync_parent_directory=True,
        )
        claim.commit()
    marker_path = os.path.join(target, ".soai_install_in_progress")
    unlink_if_exists(marker_path)
