"""SoAI - Encrypted licensing deployment identity [backend/database/repositories/licensing/deployment_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

import aiosqlite
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.licensing.identifiers import require_canonical_uuid4
from core.licensing.storage_records import DeploymentKeypair
from core.serialization.json import serialize_json_compact_stable_strict
from database.core.json_codec import safe_json_deserialize

__all__ = (
    "DeploymentIdentityRotation",
    "read_deployment_identity_query",
    "sync_has_bound_licensing_state",
    "sync_get_or_create_deployment_identity",
    "sync_resolve_instance_id",
    "sync_rotate_deployment_identity",
)

_BOUND_LICENSING_STATE_SQL = """SELECT EXISTS(
    SELECT 1 FROM licensing_operations
    UNION ALL SELECT 1 FROM licensing_documents
    UNION ALL SELECT 1 FROM licensing_offline_requests
    UNION ALL SELECT 1 FROM licensing_deployment_transitions
    ) AS bound_state"""


@dataclass(frozen=True, slots=True)
class DeploymentIdentityRotation:
    old_keypair: DeploymentKeypair
    new_public_key: bytes


def sync_resolve_instance_id(connection: sqlite3.Connection, candidate: str) -> str:
    require_canonical_uuid4(candidate)
    row = connection.execute(
        "SELECT value FROM webui_system_settings WHERE key = 'instance.id'"
    ).fetchone()
    if row is not None:
        stored = safe_json_deserialize(row[0], None)
        if isinstance(stored, str):
            valid_stored = _valid_instance_id(stored)
            if valid_stored is not None:
                return valid_stored
        if sync_has_bound_licensing_state(connection):
            raise ValidationError("Bound licensing state has an invalid instance identity.")
    connection.execute(
        """INSERT INTO webui_system_settings (key, value) VALUES ('instance.id', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (serialize_json_compact_stable_strict(candidate),),
    )
    return candidate


def _valid_instance_id(value: str) -> str | None:
    try:
        return require_canonical_uuid4(value)
    except ValidationError:
        return None


def sync_has_bound_licensing_state(connection: sqlite3.Connection) -> bool:
    row = connection.execute(_BOUND_LICENSING_STATE_SQL).fetchone()
    return row is not None and row[0] == 1


def sync_get_or_create_deployment_identity(
    connection: sqlite3.Connection,
    fernets: Sequence[Fernet],
    created_at_ms: int,
) -> DeploymentKeypair:
    if not fernets:
        raise StateError("Licensing deployment identity requires an encryption keyring.")
    row = connection.execute("""SELECT public_key, encrypted_private_key, key_algorithm, key_version
        FROM licensing_deployment_identity WHERE singleton = 1""").fetchone()
    if row is None:
        if sync_has_bound_licensing_state(connection):
            raise SecurityError("Bound licensing state has no deployment identity.")
        candidate = Ed25519PrivateKey.generate()
        private_bytes = candidate.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        public_bytes = candidate.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        encrypted = fernets[0].encrypt(private_bytes)
        connection.execute(
            """INSERT OR IGNORE INTO licensing_deployment_identity (
            singleton, public_key, encrypted_private_key, key_algorithm, key_version, created_at_ms
            ) VALUES (1, ?, ?, 'ed25519', 1, ?)""",
            (public_bytes, encrypted, created_at_ms),
        )
        row = connection.execute(
            """SELECT public_key, encrypted_private_key, key_algorithm, key_version
            FROM licensing_deployment_identity WHERE singleton = 1"""
        ).fetchone()
    if row is None:
        raise StateError("Licensing deployment identity could not be persisted.")
    return _deployment_keypair(
        bytes(row[0]),
        bytes(row[1]),
        row[2],
        row[3],
        fernets,
    )


def sync_rotate_deployment_identity(
    connection: sqlite3.Connection,
    fernets: Sequence[Fernet],
    *,
    expected_public_key: bytes,
    created_at_ms: int,
) -> DeploymentIdentityRotation:
    if not fernets:
        raise StateError("Licensing deployment identity requires an encryption keyring.")
    row = connection.execute(
        """SELECT public_key, encrypted_private_key, key_algorithm, key_version, created_at_ms
        FROM licensing_deployment_identity WHERE singleton = 1"""
    ).fetchone()
    if row is None:
        raise SecurityError("Bound licensing state has no deployment identity.")
    old_public_key = bytes(row[0])
    encrypted_private_key = bytes(row[1])
    old_keypair = _deployment_keypair(
        old_public_key,
        encrypted_private_key,
        str(row[2]),
        int(row[3]),
        fernets,
    )
    if not hmac.compare_digest(old_public_key, expected_public_key):
        raise SecurityError("Deployment rehost request does not match the current identity.")
    if created_at_ms <= int(row[4]):
        raise StateError("Deployment rehost completion must advance the identity timestamp.")
    candidate = Ed25519PrivateKey.generate()
    private_bytes = candidate.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    new_public_key = candidate.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    if hmac.compare_digest(old_public_key, new_public_key):
        raise StateError("Deployment identity rotation did not produce a distinct key.")
    encrypted_candidate = fernets[0].encrypt(private_bytes)
    updated = connection.execute(
        """UPDATE licensing_deployment_identity
        SET public_key = ?, encrypted_private_key = ?, created_at_ms = ?
        WHERE singleton = 1 AND public_key = ? AND encrypted_private_key = ?
        AND key_algorithm = ? AND key_version = ? AND created_at_ms = ?""",
        (
            new_public_key,
            encrypted_candidate,
            created_at_ms,
            old_public_key,
            encrypted_private_key,
            row[2],
            row[3],
            row[4],
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Deployment identity changed during rehost rotation.")
    return DeploymentIdentityRotation(old_keypair, new_public_key)


async def read_deployment_identity_query(
    connection: aiosqlite.Connection,
    fernets: Sequence[Fernet],
) -> DeploymentKeypair | None:
    cursor = await connection.execute(
        """SELECT public_key, encrypted_private_key, key_algorithm, key_version
        FROM licensing_deployment_identity WHERE singleton = 1"""
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _deployment_keypair(bytes(row[0]), bytes(row[1]), row[2], row[3], fernets)


def _deployment_keypair(
    public_bytes: bytes,
    encrypted_private: bytes,
    key_algorithm: str,
    key_version: int,
    fernets: Sequence[Fernet],
) -> DeploymentKeypair:
    if key_algorithm != "ed25519" or key_version != 1:
        raise SecurityError("Licensing deployment key contract is invalid.")
    private_bytes = _decrypt_private_key(fernets, encrypted_private)
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    except ValueError as exception:
        raise SecurityError("Licensing deployment private key is invalid.") from exception
    derived_public = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    if not hmac.compare_digest(derived_public, public_bytes):
        raise SecurityError("Licensing deployment private key does not match its public key.")
    return DeploymentKeypair(private_key=private_key, public_key=public_bytes)


def _decrypt_private_key(fernets: Sequence[Fernet], encrypted: bytes) -> bytes:
    for fernet in fernets:
        try:
            return fernet.decrypt(encrypted)
        except InvalidToken:
            continue
    raise SecurityError("Licensing deployment private key cannot be decrypted.")
