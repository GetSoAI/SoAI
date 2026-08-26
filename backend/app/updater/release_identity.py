"""SoAI - Official Core release identity validation [backend/app/updater/release_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from app.updater.release_manifest_types import (
    ReleaseIdentity,
    ReleaseLegalFingerprint,
    ReleasePublicationRecord,
    ReleasePublicTrust,
)
from core.errors.exceptions import ValidationError
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.types.json_value import require_json_dict_list
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "parse_legal_fingerprints",
    "parse_public_trust",
    "parse_release_identity",
)


def _exact_fields(payload: JSONDict, fields: frozenset[str], label: str) -> None:
    if frozenset(payload) != fields:
        raise ValidationError(f"{label} fields do not match the V1 contract.")


def _commit(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}\Z", value) is None:
        raise ValidationError(f"{field} must be a canonical Git SHA-1 object ID.")
    return value


def _date(value: JSONValue, field: str) -> date:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO calendar date.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exception:
        raise ValidationError(f"{field} must be an ISO calendar date.") from exception
    if parsed.isoformat() != value:
        raise ValidationError(f"{field} must be an ISO calendar date.")
    return parsed


def _expected_change_date(publication_date: date) -> date:
    try:
        return publication_date.replace(year=publication_date.year + 4)
    except ValueError:
        return publication_date.replace(year=publication_date.year + 4, day=28)


def _publication_record(
    payload: JSONDict,
    expected_version: str,
    publication_date: date,
    change_date: date,
) -> ReleasePublicationRecord:
    _exact_fields(
        payload,
        frozenset(
            {
                "public_core_commit",
                "first_publication_release",
                "first_publication_date",
                "change_date",
            }
        ),
        "Historical publication record",
    )
    record_release = coerce_required_non_empty_str(
        payload.get("first_publication_release"),
        label="historical first-publication release",
    )
    record_publication = _date(
        payload.get("first_publication_date"),
        "historical first_publication_date",
    )
    record_change = _date(payload.get("change_date"), "historical change_date")
    if (
        record_release != expected_version
        or record_publication != publication_date
        or record_change != change_date
    ):
        raise ValidationError(
            "Newly exposed commits must receive this release's publication and Change Dates."
        )
    return ReleasePublicationRecord(
        public_core_commit=_commit(
            payload.get("public_core_commit"),
            "historical public_core_commit",
        ),
        first_publication_release=record_release,
        first_publication_date=record_publication.isoformat(),
        change_date=record_change.isoformat(),
    )


def parse_release_identity(value: JSONValue, expected_version: str) -> ReleaseIdentity:
    if not isinstance(value, dict):
        raise ValidationError("release_identity must be an object.")
    _exact_fields(
        value,
        frozenset(
            {
                "public_core_commit",
                "immutable_tag",
                "first_publication_date",
                "change_date",
                "newly_exposed_core_commits",
            }
        ),
        "Release identity",
    )
    publication_date = _date(value.get("first_publication_date"), "first_publication_date")
    change_date = _date(value.get("change_date"), "change_date")
    if change_date != _expected_change_date(publication_date):
        raise ValidationError("Change Date must be exactly four years after first publication.")
    immutable_tag = coerce_required_non_empty_str(
        value.get("immutable_tag"),
        label="immutable release tag",
    )
    if immutable_tag != f"v{expected_version}":
        raise ValidationError("Immutable release tag must exactly match the numbered release.")
    current_commit = _commit(value.get("public_core_commit"), "public_core_commit")
    records = tuple(
        _publication_record(entry, expected_version, publication_date, change_date)
        for entry in require_json_dict_list(
            value.get("newly_exposed_core_commits"),
            label="newly_exposed_core_commits",
        )
    )
    commits = tuple(record.public_core_commit for record in records)
    if commits != tuple(sorted(commits)) or len(commits) != len(set(commits)):
        raise ValidationError("Newly exposed Core commits must be unique and sorted.")
    if current_commit in commits:
        raise ValidationError("Current public Core commit is not a historical publication record.")
    return ReleaseIdentity(
        public_core_commit=current_commit,
        immutable_tag=immutable_tag,
        first_publication_date=publication_date.isoformat(),
        change_date=change_date.isoformat(),
        newly_exposed_core_commits=records,
    )


def _sha256(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or not is_canonical_sha256_hexdigest(value):
        raise ValidationError(f"{field} must be a canonical SHA-256 digest.")
    return value


def parse_legal_fingerprints(value: JSONValue) -> tuple[ReleaseLegalFingerprint, ...]:
    records: list[ReleaseLegalFingerprint] = []
    for entry in require_json_dict_list(value, label="legal_fingerprints"):
        _exact_fields(entry, frozenset({"document_id", "sha256"}), "Legal fingerprint")
        document_id = coerce_required_non_empty_str(
            entry.get("document_id"),
            label="legal document ID",
        )
        if re.fullmatch(r"[a-z][a-z0-9_]*\Z", document_id) is None:
            raise ValidationError("Legal document ID is invalid.")
        records.append(
            ReleaseLegalFingerprint(
                document_id=document_id,
                sha256=_sha256(entry.get("sha256"), f"{document_id}.sha256"),
            )
        )
    identifiers = tuple(record.document_id for record in records)
    if not identifiers or identifiers != tuple(sorted(identifiers)):
        raise ValidationError("Legal fingerprints must be non-empty and sorted by document ID.")
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("Legal fingerprints contain a duplicate document ID.")
    return tuple(records)


def parse_public_trust(value: JSONValue) -> ReleasePublicTrust:
    if not isinstance(value, dict):
        raise ValidationError("public_trust must be an object.")
    fields = frozenset(
        {
            "release_signing_key_sha256",
            "licensing_root_key_sha256",
            "licensing_issuer_catalog_sha256",
        }
    )
    _exact_fields(value, fields, "Release public trust")
    return ReleasePublicTrust(
        release_signing_key_sha256=_sha256(
            value.get("release_signing_key_sha256"),
            "release_signing_key_sha256",
        ),
        licensing_root_key_sha256=_sha256(
            value.get("licensing_root_key_sha256"),
            "licensing_root_key_sha256",
        ),
        licensing_issuer_catalog_sha256=_sha256(
            value.get("licensing_issuer_catalog_sha256"),
            "licensing_issuer_catalog_sha256",
        ),
    )
