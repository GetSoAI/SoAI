"""SoAI - Exact governing-document records [backend/core/licensing/governing_documents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.licensing.legal_documents import load_legal_catalog
from core.licensing.policy import EditionLicensingPolicy
from core.types.json import JSONValue
from core.validation.object_fields import require_exact_json_fields

__all__ = (
    "GoverningDocument",
    "parse_governing_documents",
    "require_cataloged_governing_documents",
)

_FIELDS = frozenset(("document_id", "fingerprint", "version"))


@dataclass(frozen=True, slots=True)
class GoverningDocument:
    document_id: str
    fingerprint: str
    version: str


def parse_governing_documents(value: JSONValue) -> tuple[GoverningDocument, ...]:
    if not isinstance(value, list) or not value:
        raise ValidationError("Licensing governing documents must be a non-empty array.")
    records = tuple(_parse_record(record) for record in value)
    identities = tuple(record.document_id for record in records)
    if identities != tuple(sorted(set(identities))):
        raise ValidationError("Licensing governing documents must be sorted and unique.")
    return records


def require_cataloged_governing_documents(
    project_root: str,
    policy: EditionLicensingPolicy,
    documents: tuple[GoverningDocument, ...],
) -> None:
    catalog = {
        record.document_id: record
        for record in load_legal_catalog(project_root, policy.legal_catalog_relative_paths)
    }
    for document in documents:
        cataloged = catalog.get(document.document_id)
        if (
            cataloged is None
            or document.fingerprint != f"sha256:{cataloged.sha256}"
            or document.version != cataloged.version
        ):
            raise ValidationError("Licensing governing document is not current.")


def _parse_record(value: JSONValue) -> GoverningDocument:
    if not isinstance(value, dict):
        raise ValidationError("Licensing governing-document record must be an object.")
    require_exact_json_fields(
        value,
        allowed_fields=_FIELDS,
        label="Governing document",
    )
    document_id = value.get("document_id")
    fingerprint = value.get("fingerprint")
    version = value.get("version")
    if (
        not isinstance(document_id, str)
        or re.fullmatch(r"[a-z][a-z0-9_]{1,63}", document_id) is None
    ):
        raise ValidationError("Licensing governing-document record is invalid.")
    if (
        not isinstance(fingerprint, str)
        or re.fullmatch(r"sha256:[a-f0-9]{64}", fingerprint) is None
    ):
        raise ValidationError("Licensing governing-document record is invalid.")
    if not isinstance(version, str) or re.fullmatch(r"[1-9][0-9]*\.[0-9]+", version) is None:
        raise ValidationError("Licensing governing-document record is invalid.")
    return GoverningDocument(document_id, fingerprint, version)
