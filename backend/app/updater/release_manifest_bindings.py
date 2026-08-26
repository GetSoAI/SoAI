"""SoAI - Release identity-to-archive bindings [backend/app/updater/release_manifest_bindings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.updater.release_manifest_types import ReleaseManifestV1
from core.errors.exceptions import ValidationError

__all__ = ("validate_release_manifest_bindings",)


def validate_release_manifest_bindings(manifest: ReleaseManifestV1) -> None:
    legal_paths = (
        ("soai_core_change_dates", "CHANGE-DATES.md"),
        ("soai_core_license", "LICENSE.md"),
        ("commercial_support_terms", "COMMERCIAL-SUPPORT-TERMS.md"),
        ("organization_evaluation_terms", "ORGANIZATION-EVALUATION-TERMS.md"),
        ("personal_os_purchase_terms", "soai_os/licenses/PERSONAL-PURCHASE-TERMS.md"),
        ("soai_os_license", "soai_os/licenses/LICENSE.md"),
        ("standard_commercial_license", "COMMERCIAL-LICENSE.md"),
    )
    legal_path_by_id = dict(legal_paths)
    expected_legal_ids = frozenset(
        document_id
        for document_id, path in legal_paths
        if manifest.edition == "soai-os" or not path.startswith("soai_os/")
    )
    legal_by_id = {record.document_id: record.sha256 for record in manifest.legal_fingerprints}
    if frozenset(legal_by_id) != expected_legal_ids:
        raise ValidationError("Release legal fingerprints do not match the edition.")
    trust_bindings = (
        (
            "backend/core/licensing/trust/licensing_root_ed25519_public_key.bin",
            manifest.public_trust.licensing_root_key_sha256,
        ),
        (
            "backend/core/licensing/trust/issuer_authorizations_v1.json",
            manifest.public_trust.licensing_issuer_catalog_sha256,
        ),
    )
    for archive in manifest.update_archives:
        file_digests = {record.path: record.sha256 for record in archive.files}
        for document_id, digest in legal_by_id.items():
            if file_digests.get(legal_path_by_id[document_id]) != digest:
                raise ValidationError(f"Release archive legal binding is invalid: {archive.name}")
        for path, digest in trust_bindings:
            if file_digests.get(path) != digest:
                raise ValidationError(
                    f"Release archive licensing trust binding is invalid: {archive.name}"
                )
