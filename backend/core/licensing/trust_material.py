"""SoAI - Immutable release trust material loading [backend/core/licensing/trust_material.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.licensing.trust import IssuerAuthorizationCatalog, load_issuer_authorization_catalog

ROOT_PUBLIC_KEY_PATH = "backend/core/licensing/trust/licensing_root_ed25519_public_key.bin"
ISSUER_CATALOG_PATH = "backend/core/licensing/trust/issuer_authorizations_v1.json"


@dataclass(frozen=True, slots=True)
class ReleaseTrustMaterial:
    catalog: IssuerAuthorizationCatalog | None

    def require_catalog(self) -> IssuerAuthorizationCatalog:
        if self.catalog is None:
            raise StateError("Production licensing trust material is unavailable.")
        return self.catalog


def load_release_trust_material(project_root: str) -> IssuerAuthorizationCatalog:
    root_key = _read_regular_bounded(project_root, ROOT_PUBLIC_KEY_PATH, 32)
    if len(root_key) != 32:
        raise StateError("Licensing root trust material is unavailable or invalid.")
    catalog = _read_regular_bounded(project_root, ISSUER_CATALOG_PATH, 65_536)
    return load_issuer_authorization_catalog(root_key, catalog)


def resolve_release_trust_material(project_root: str) -> ReleaseTrustMaterial:
    try:
        catalog = load_release_trust_material(project_root)
    except (StateError, ValidationError):
        catalog = None
    return ReleaseTrustMaterial(catalog)


def _read_regular_bounded(project_root: str, relative_path: str, maximum: int) -> bytes:
    try:
        opened = open_managed_file_descriptor(
            project_root,
            os.path.join(project_root, relative_path),
        )
    except FileStorageSecurityError as exception:
        raise StateError(
            "Required production licensing trust material is unavailable."
        ) from exception
    if opened.size_bytes > maximum:
        os.close(opened.descriptor)
        raise StateError("Required production licensing trust material exceeds its limit.")
    with os.fdopen(opened.descriptor, "rb") as source:
        content = source.read(maximum + 1)
    if len(content) > maximum:
        raise StateError("Required production licensing trust material exceeds its limit.")
    return content


__all__ = (
    "ISSUER_CATALOG_PATH",
    "ROOT_PUBLIC_KEY_PATH",
    "ReleaseTrustMaterial",
    "load_release_trust_material",
    "resolve_release_trust_material",
)
