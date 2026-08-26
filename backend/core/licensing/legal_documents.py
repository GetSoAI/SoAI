"""SoAI - Canonical legal catalog and exact document loading [backend/core/licensing/legal_documents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, ValidationError
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.licensing.policy import EditionLicensingPolicy

__all__ = (
    "LegalDocumentRecord",
    "LicensingDocument",
    "load_edition_flow_documents",
    "load_legal_catalog",
    "load_licensing_document",
    "validate_edition_licensing_documents",
)

_FLOW_IDS = frozenset(
    (
        "core_evaluation",
        "commercial_activation",
        "os_evaluation_conversion",
        "personal_os_activation",
    )
)

_CORE_CATALOG_PATHS = ("licenses/legal_document_catalog.json",)
_MAX_LEGAL_DOCUMENT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class LegalDocumentRecord:
    document_id: str
    repository_path: str
    version: str
    effective_date: str
    sha256: str
    flows: tuple[str, ...]
    offers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LicensingDocument:
    content: bytes
    fingerprint: str


def load_legal_catalog(
    project_root: str,
    catalog_relative_paths: tuple[str, ...] = _CORE_CATALOG_PATHS,
) -> tuple[LegalDocumentRecord, ...]:
    if not catalog_relative_paths or len(set(catalog_relative_paths)) != len(
        catalog_relative_paths
    ):
        raise ValidationError("Legal-document catalog paths are invalid.")
    records = tuple(
        record
        for catalog_path in catalog_relative_paths
        for record in _load_legal_catalog_file(project_root, catalog_path)
    )
    if (
        not records
        or len({record.document_id for record in records}) != len(records)
        or len({record.repository_path for record in records}) != len(records)
    ):
        raise ValidationError("Legal-document catalog inventory is invalid.")
    return records


def _load_legal_catalog_file(
    project_root: str,
    catalog_relative_path: str,
) -> tuple[LegalDocumentRecord, ...]:
    _repository_path(catalog_relative_path)
    content = _read_bounded_document(project_root, catalog_relative_path)
    try:
        payload = parse_json_dict(
            content,
            field="legal-document catalog",
            reject_duplicate_keys=True,
        )
    except ValidationError as exception:
        raise ValidationError("Legal-document catalog is not valid JSON.") from exception
    if not isinstance(payload, dict) or set(payload) != {
        "catalog_version",
        "documents",
        "schema_version",
    }:
        raise ValidationError("Legal-document catalog fields are invalid.")
    if payload["schema_version"] != 1 or payload["catalog_version"] != "1.0":
        raise ValidationError("Legal-document catalog identity is invalid.")
    documents = payload["documents"]
    if not isinstance(documents, list):
        raise ValidationError("Legal-document catalog records are invalid.")
    records = tuple(_parse_record(document) for document in documents)
    if not records or len({record.document_id for record in records}) != len(records):
        raise ValidationError("Legal-document catalog inventory is invalid.")
    return records


def load_licensing_document(
    project_root: str,
    relative_path: str,
    catalog_relative_paths: tuple[str, ...] = _CORE_CATALOG_PATHS,
) -> LicensingDocument:
    records = load_legal_catalog(project_root, catalog_relative_paths)
    matching = tuple(record for record in records if record.repository_path == relative_path)
    if len(matching) != 1:
        raise ValidationError("Legal document is not present in the canonical catalog.")
    record = matching[0]
    content = _read_bounded_document(project_root, relative_path)
    digest = hashlib.sha256(content).hexdigest()
    if digest != record.sha256:
        raise ValidationError("Legal document does not match the canonical catalog.")
    return LicensingDocument(content=content, fingerprint=f"sha256:{digest}")


def load_edition_flow_documents(
    project_root: str,
    policy: EditionLicensingPolicy,
    flow: str,
) -> tuple[tuple[LegalDocumentRecord, LicensingDocument], ...]:
    edition = policy.edition
    if edition not in {"soai-core", "soai-os"} or flow not in _FLOW_IDS:
        raise ValidationError("Licensing legal-document flow is invalid.")
    if edition == "soai-core" and flow not in {"core_evaluation", "commercial_activation"}:
        raise ValidationError("Licensing legal-document flow is unavailable for this edition.")
    if edition == "soai-os" and flow == "core_evaluation":
        raise ValidationError("Licensing legal-document flow is unavailable for this edition.")
    catalog = load_legal_catalog(project_root, policy.legal_catalog_relative_paths)
    _validate_policy_inventory(catalog, policy)
    records = tuple(record for record in catalog if flow in record.flows)
    records = tuple(sorted(records, key=lambda record: record.document_id))
    if not records:
        raise ValidationError("Licensing legal-document flow has no governing documents.")
    return tuple(
        (
            record,
            load_licensing_document(
                project_root,
                record.repository_path,
                policy.legal_catalog_relative_paths,
            ),
        )
        for record in records
    )


def validate_edition_licensing_documents(
    project_root: str,
    policy: EditionLicensingPolicy,
) -> LicensingDocument:
    records = load_legal_catalog(project_root, policy.legal_catalog_relative_paths)
    _validate_policy_inventory(records, policy)
    for record in records:
        load_licensing_document(
            project_root,
            record.repository_path,
            policy.legal_catalog_relative_paths,
        )
    return load_licensing_document(
        project_root,
        policy.controlling_license_relative_path,
        policy.legal_catalog_relative_paths,
    )


def _validate_policy_inventory(
    records: tuple[LegalDocumentRecord, ...],
    policy: EditionLicensingPolicy,
) -> None:
    if frozenset(record.document_id for record in records) != policy.legal_document_ids:
        raise ValidationError("Legal-document catalog contradicts edition policy.")


def _parse_record(value: JSONValue) -> LegalDocumentRecord:
    if not isinstance(value, dict) or set(value) != {
        "document_id",
        "effective_date",
        "flows",
        "offers",
        "repository_path",
        "sha256",
        "version",
    }:
        raise ValidationError("Legal-document catalog record fields are invalid.")
    document_id = _ascii_identifier(value["document_id"], "document identity")
    version = _ascii_value(value["version"], "document version")
    effective_date = _ascii_value(value["effective_date"], "document effective date")
    repository_path = _repository_path(value["repository_path"])
    sha256 = value["sha256"]
    if not isinstance(sha256, str) or re.fullmatch(r"[a-f0-9]{64}", sha256) is None:
        raise ValidationError("Legal-document catalog fingerprint is invalid.")
    return LegalDocumentRecord(
        document_id=document_id,
        repository_path=repository_path,
        version=version,
        effective_date=effective_date,
        sha256=sha256,
        flows=_string_list(value["flows"], "flow"),
        offers=_string_list(value["offers"], "offer"),
    )


def _string_list(value: JSONValue, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValidationError(f"Legal-document catalog {field} list is invalid.")
    entries = tuple(_ascii_identifier(entry, field) for entry in value)
    if len(set(entries)) != len(entries):
        raise ValidationError(f"Legal-document catalog {field} list contains duplicates.")
    return entries


def _ascii_identifier(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value) is None:
        raise ValidationError(f"Legal-document catalog {field} is invalid.")
    return value


def _ascii_value(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 32 or not value.isascii():
        raise ValidationError(f"Legal-document catalog {field} is invalid.")
    return value


def _repository_path(value: JSONValue) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValidationError("Legal-document catalog path is invalid.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValidationError("Legal-document catalog path is invalid.")
    return value


def _read_bounded_document(project_root: str, relative_path: str) -> bytes:
    document_path = os.path.join(project_root, relative_path)
    try:
        opened = open_managed_file_descriptor(project_root, document_path)
    except FileStorageSecurityError as exception:
        if not os.path.exists(document_path):
            raise NotFoundError("Required licensing document is unavailable.") from exception
        raise ValidationError(
            "Required licensing document is not a regular project file."
        ) from exception
    if opened.size_bytes > _MAX_LEGAL_DOCUMENT_BYTES:
        os.close(opened.descriptor)
        raise ValidationError("Required licensing document exceeds its size limit.")
    with os.fdopen(opened.descriptor, "rb") as source:
        content = source.read(_MAX_LEGAL_DOCUMENT_BYTES + 1)
    if not content or len(content) > _MAX_LEGAL_DOCUMENT_BYTES:
        raise ValidationError("Required licensing document size is invalid.")
    try:
        content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise ValidationError("Required licensing document must be UTF-8.") from exception
    return content
