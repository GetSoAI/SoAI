"""SoAI - Cryptographic staged licensing state validation [backend/core/licensing/backup_state_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hmac
import sqlite3

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.errors.exceptions import StateError, ValidationError
from core.licensing.canonicalization import parse_canonical_licensing_document
from core.licensing.entitlement_payloads import ParsedEntitlementPayload, parse_entitlement_payload
from core.licensing.entitlement_validation import (
    EntitlementBinding,
    ValidatedEntitlement,
    validate_entitlement,
)
from core.licensing.licensing_status_validation import (
    LicensingStatusBinding,
    validate_signed_licensing_status,
)
from core.licensing.offline_entitlement_validation import (
    OfflineEntitlementBinding,
    validate_offline_entitlement,
)
from core.licensing.trust import IssuerAuthorizationCatalog
from core.licensing.types import Edition
from core.meta.instance_identity import INSTANCE_ID_SETTING_KEY
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue


def validate_active_licensing_state(
    connection: sqlite3.Connection,
    catalog: IssuerAuthorizationCatalog,
    deployment_public_key: bytes,
) -> None:
    entitlement = connection.execute(
        """SELECT document_digest, canonical_content, document_type, entitlement_type,
        entitlement_id, license_id, deployment_id, generation,
        issuer_authorization_snapshot FROM licensing_documents
        WHERE disposition = 'active' AND document_type != 'licensing_status'"""
    ).fetchone()
    status = connection.execute("""SELECT canonical_content, license_id, deployment_id, generation,
        issuer_authorization_snapshot FROM licensing_documents
        WHERE disposition = 'active' AND document_type = 'licensing_status'""").fetchone()
    if entitlement is None:
        if status is not None:
            raise StateError("Active licensing status has no active entitlement.")
        return
    edition = read_snapshot_licensing_edition(connection)
    instance_id = read_snapshot_instance_id(connection)
    if entitlement[2] == "offline_entitlement":
        _validate_offline(
            connection,
            catalog,
            deployment_public_key,
            edition,
            instance_id,
            entitlement,
        )
        if status is not None:
            raise StateError("Offline entitlement cannot carry an online licensing status.")
        return
    if entitlement[2] != "entitlement":
        raise StateError("Active licensing document type is invalid.")
    validated, payload = _validate_online(
        catalog,
        deployment_public_key,
        edition,
        instance_id,
        entitlement,
    )
    if status is not None:
        _validate_status(catalog, instance_id, entitlement, validated, payload, status)


def _validate_online(
    catalog: IssuerAuthorizationCatalog,
    deployment_public_key: bytes,
    edition: Edition,
    instance_id: str,
    row: sqlite3.Row,
) -> tuple[ValidatedEntitlement, ParsedEntitlementPayload]:
    envelope = _object(parse_canonical_licensing_document(bytes(row[1])))
    signature_domain = envelope.get("signature_domain")
    if not isinstance(signature_domain, str):
        raise StateError("Stored licensing entitlement signature domain is invalid.")
    payload = parse_entitlement_payload(envelope.get("payload"), signature_domain)
    validated = validate_entitlement(
        bytes(row[1]),
        catalog,
        EntitlementBinding(
            edition=edition,
            instance_id=instance_id,
            deployment_public_key=deployment_public_key,
            current_deployment_id=str(row[6]),
            current_generation=int(row[7]),
            current_document=bytes(row[1]),
        ),
        bytes(row[8]),
    )
    stored_metadata = (row[0], row[3], row[4], row[5], row[6], row[7])
    validated_metadata = (
        validated.document_digest,
        validated.entitlement_type,
        payload.values.get("evaluation_id"),
        payload.values.get("license_id"),
        validated.deployment_id,
        validated.generation,
    )
    if stored_metadata != validated_metadata:
        raise StateError("Stored licensing entitlement metadata is invalid.")
    return validated, payload


def _validate_offline(
    connection: sqlite3.Connection,
    catalog: IssuerAuthorizationCatalog,
    deployment_public_key: bytes,
    edition: Edition,
    instance_id: str,
    row: sqlite3.Row,
) -> None:
    request = connection.execute("""SELECT instance_id, deployment_public_key, request_digest
        FROM licensing_offline_requests WHERE singleton = 1""").fetchone()
    if request is None or request[0] != instance_id or bytes(request[1]) != deployment_public_key:
        raise StateError("Stored offline entitlement request binding is invalid.")
    root_public = catalog.root_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    validated = validate_offline_entitlement(
        bytes(row[1]),
        root_public,
        OfflineEntitlementBinding(
            edition=edition,
            instance_id=instance_id,
            deployment_public_key=deployment_public_key,
            customer_request_digest=str(request[2]),
            current_deployment_id=str(row[6]),
            current_generation=int(row[7]),
            current_document=bytes(row[1]),
        ),
    )
    stored_metadata = (row[0], row[3], row[4], row[5], row[6], row[7])
    validated_metadata = (
        validated.document_digest,
        validated.entitlement_type,
        validated.allocation_id,
        validated.license_id,
        validated.deployment_id,
        validated.generation,
    )
    snapshot_matches = isinstance(row[8], bytes) and hmac.compare_digest(
        bytes(row[8]), validated.root_snapshot
    )
    if stored_metadata != validated_metadata or not snapshot_matches:
        raise StateError("Stored offline entitlement metadata or trust snapshot is invalid.")


def _validate_status(
    catalog: IssuerAuthorizationCatalog,
    instance_id: str,
    entitlement: sqlite3.Row,
    validated: ValidatedEntitlement,
    payload: ParsedEntitlementPayload,
    status: sqlite3.Row,
) -> None:
    license_id = payload.values.get("license_id")
    if not isinstance(license_id, str):
        raise StateError("Stored licensing status has no commercial license binding.")
    checked = validate_signed_licensing_status(
        bytes(status[0]),
        catalog,
        LicensingStatusBinding(
            instance_id=instance_id,
            deployment_id=validated.deployment_id,
            license_id=license_id,
            entitlement_type=validated.entitlement_type,
            licensed_product_scope=validated.licensed_product_scope,
            current_generation=int(status[3]),
            current_document=bytes(status[0]),
        ),
        bytes(status[4]),
    )
    if (
        status[1] != license_id
        or status[2] != entitlement[6]
        or status[3] != checked.generation
        or checked.generation <= entitlement[7]
    ):
        raise StateError("Stored licensing status metadata is invalid.")


def read_snapshot_licensing_edition(connection: sqlite3.Connection) -> Edition:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'licensing_wizard_draft'"
    ).fetchone()
    if table is None:
        raise StateError("Bound licensing state has no edition storage.")
    row = connection.execute(
        "SELECT edition FROM licensing_wizard_draft WHERE singleton = 1"
    ).fetchone()
    if row is None or row[0] not in {"soai-core", "soai-os"}:
        raise StateError("Bound licensing state has no valid edition binding.")
    if row[0] == "soai-core":
        return "soai-core"
    return "soai-os"


def read_snapshot_instance_id(connection: sqlite3.Connection) -> str:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'webui_system_settings'"
    ).fetchone()
    if table is None:
        raise StateError("Bound licensing state has no instance identity storage.")
    row = connection.execute(
        "SELECT value FROM webui_system_settings WHERE key = ?",
        (INSTANCE_ID_SETTING_KEY,),
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        raise StateError("Bound licensing state has no instance identity.")
    try:
        decoded = parse_json_value(row[0], field="stored instance identity")
    except ValidationError as exception:
        raise StateError("Bound licensing state has an invalid instance identity.") from exception
    if not isinstance(decoded, str):
        raise StateError("Bound licensing state has an invalid instance identity.")
    return decoded


def _object(value: JSONValue) -> JSONDict:
    if not isinstance(value, dict):
        raise ValidationError("Stored licensing document must be an object.")
    return value


__all__ = (
    "read_snapshot_instance_id",
    "read_snapshot_licensing_edition",
    "validate_active_licensing_state",
)
