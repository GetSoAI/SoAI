"""SoAI - Licensing backup-pair recovery validation [backend/core/licensing/backup_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from typing import Literal, TypedDict

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.licensing.backup_operation_validation import (
    validate_persisted_operations,
    validate_persisted_request,
)
from core.licensing.backup_state_validation import (
    read_snapshot_instance_id,
    read_snapshot_licensing_edition,
    validate_active_licensing_state,
)
from core.licensing.canonicalization import parse_canonical_licensing_document
from core.licensing.deployment_transition_validation import (
    validate_deployment_transition_lineage,
)
from core.licensing.trust import IssuerAuthorizationCatalog
from core.licensing.types import Edition
from core.sqlite.connections import connect_sqlite
from core.sqlite.policy import resolve_sqlite_database_target
from core.types.json import JSONValue


class LicensingRecoveryTarget(TypedDict):
    present: bool
    sha256: str | None


class LicensingRecoverySummary(TypedDict):
    state: Literal["not_applicable", "complete", "incomplete"]
    database: LicensingRecoveryTarget
    encryption_key: LicensingRecoveryTarget


def snapshot_has_bound_licensing_state(database_path: str) -> bool:
    connection = _open_read_only_database(database_path)
    try:
        return _connection_has_bound_state(connection)
    finally:
        connection.close()


def validate_licensing_recovery_edition(
    database_path: str,
    expected_edition: Edition,
) -> None:
    connection = _open_read_only_database(database_path)
    try:
        if _connection_has_bound_state(connection):
            _require_expected_edition(connection, expected_edition)
        else:
            _require_expected_edition_if_present(connection, expected_edition)
    finally:
        connection.close()


def validate_licensing_recovery_pair(
    database_path: str,
    encryption_key_path: str,
    expected_edition: Edition,
    trust_catalog: IssuerAuthorizationCatalog | None = None,
) -> None:
    connection = _open_read_only_database(database_path)
    try:
        if not _connection_has_bound_state(connection):
            _require_expected_edition_if_present(connection, expected_edition)
            return
        row = (
            connection.execute(
                """SELECT public_key, encrypted_private_key, key_algorithm, key_version, created_at_ms
                FROM licensing_deployment_identity WHERE singleton = 1"""
            ).fetchone()
            if _table_exists(connection, "licensing_deployment_identity")
            else None
        )
        if row is None:
            raise StateError("Bound licensing state has no deployment identity.")
        _require_expected_edition(connection, expected_edition)
        if row[2] != "ed25519" or row[3] != 1:
            raise StateError("Licensing deployment identity contract is invalid.")
        public_key = bytes(row[0])
        encrypted_private_key = bytes(row[1])
        if len(public_key) != 32:
            raise StateError("Licensing deployment public key is invalid.")
        private_bytes = _decrypt_private_key(encryption_key_path, encrypted_private_key)
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        derived = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        if not hmac.compare_digest(public_key, derived):
            raise StateError("Licensing database and encryption key do not match.")
        historical_keys: frozenset[bytes] = frozenset()
        if (
            connection.execute("SELECT 1 FROM licensing_deployment_transitions LIMIT 1").fetchone()
            is not None
        ):
            historical_keys = validate_deployment_transition_lineage(
                connection,
                catalog=trust_catalog,
                edition=expected_edition,
                instance_id=read_snapshot_instance_id(connection),
                current_public_key=public_key,
                current_key_created_at_ms=int(row[4]),
            )
        _validate_persisted_records(connection, public_key, historical_keys)
        if trust_catalog is not None:
            validate_active_licensing_state(connection, trust_catalog, public_key)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise StateError("Licensing database integrity validation failed.")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StateError("Licensing database relationship validation failed.")
    finally:
        connection.close()


def _require_expected_edition(
    connection: sqlite3.Connection,
    expected_edition: Edition,
) -> None:
    if read_snapshot_licensing_edition(connection) != expected_edition:
        raise ValidationError("Licensing recovery edition does not match this application.")


def _require_expected_edition_if_present(
    connection: sqlite3.Connection,
    expected_edition: Edition,
) -> None:
    if not _table_exists(connection, "licensing_wizard_draft"):
        return
    row = connection.execute(
        "SELECT edition FROM licensing_wizard_draft WHERE singleton = 1"
    ).fetchone()
    if row is None:
        return
    if row[0] not in {"soai-core", "soai-os"}:
        raise StateError("Stored licensing wizard edition binding is invalid.")
    if row[0] != expected_edition:
        raise ValidationError("Licensing recovery edition does not match this application.")


def _open_read_only_database(database_path: str) -> sqlite3.Connection:
    status = os.lstat(database_path)
    if not os.path.isfile(database_path) or os.path.islink(database_path) or status.st_size < 1:
        raise ValidationError("Licensing recovery database must be a non-empty regular file.")
    target, use_uri = resolve_sqlite_database_target(
        database_path,
        is_shared_memory_mode=False,
        read_only=True,
    )
    return connect_sqlite(
        target,
        timeout=5.0,
        uri=use_uri,
        must_exist=True,
    )


def _connection_has_bound_state(connection: sqlite3.Connection) -> bool:
    return any(
        _table_has_row(connection, table_name)
        for table_name in (
            "licensing_deployment_identity",
            "licensing_operations",
            "licensing_documents",
            "licensing_deployment_transitions",
        )
    )


def _table_has_row(
    connection: sqlite3.Connection,
    table_name: Literal[
        "licensing_deployment_identity",
        "licensing_operations",
        "licensing_documents",
        "licensing_deployment_transitions",
    ],
) -> bool:
    if not _table_exists(connection, table_name):
        return False
    return connection.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone() is not None


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _decrypt_private_key(path: str, encrypted: bytes) -> bytes:
    with open_regular_binary_no_symlink(path) as source:
        content = source.read(16_385)
    if len(content) > 16_384:
        raise ValidationError("Licensing recovery encryption key file is invalid.")
    keys = [line.strip() for line in content.splitlines() if line.strip()]
    for raw_key in keys:
        try:
            private_bytes = Fernet(raw_key).decrypt(encrypted)
        except (InvalidToken, ValueError):
            continue
        if len(private_bytes) == 32:
            return private_bytes
    raise StateError("Licensing deployment private key cannot be decrypted by the backup key.")


def _validate_persisted_records(
    connection: sqlite3.Connection,
    deployment_public_key: bytes,
    historical_public_keys: frozenset[bytes],
) -> None:
    documents = connection.execute(
        """SELECT document_digest, canonical_content, issuer_authorization_snapshot
        FROM licensing_documents"""
    ).fetchall()
    for digest, content, authorization in documents:
        if not isinstance(content, bytes) or not hmac.compare_digest(
            str(digest),
            f"sha256:{hashlib.sha256(content).hexdigest()}",
        ):
            raise StateError("Stored licensing document digest is invalid.")
        _require_canonical_record(content, "document digest")
        if not isinstance(authorization, bytes):
            raise StateError("Stored licensing trust snapshot is invalid.")
        _require_canonical_record(authorization, "trust snapshot")
    validate_persisted_operations(
        connection,
        deployment_public_key,
        historical_public_keys,
    )
    offline_requests = connection.execute(
        """SELECT request_digest, canonical_content, deployment_public_key
        FROM licensing_offline_requests"""
    ).fetchall()
    for digest, content, stored_public_key in offline_requests:
        if (
            not isinstance(content, bytes)
            or not isinstance(digest, str)
            or not isinstance(stored_public_key, bytes)
            or not hmac.compare_digest(stored_public_key, deployment_public_key)
        ):
            raise StateError("Stored offline licensing request binding is invalid.")
        validate_persisted_request(
            content,
            digest,
            "soai-licensing-offline-activation-request-v1",
            deployment_public_key,
        )


def _require_canonical_record(content: bytes, label: str) -> JSONValue:
    try:
        return parse_canonical_licensing_document(content)
    except ValidationError as exception:
        raise StateError(f"Stored licensing {label} is invalid.") from exception


__all__ = (
    "LicensingRecoverySummary",
    "snapshot_has_bound_licensing_state",
    "validate_licensing_recovery_edition",
    "validate_licensing_recovery_pair",
)
