"""SoAI - Staged licensing operation integrity validation [backend/core/licensing/backup_operation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.licensing.canonicalization import parse_canonical_licensing_document
from core.licensing.identifiers import require_canonical_uuid4, require_licensing_identifier
from core.licensing.machine_request_validation import validate_persisted_machine_request
from core.licensing.operation_outcomes import licensing_operation_terminal_codes

_REMOTE_OPERATIONS = frozenset(
    {
        "evaluation",
        "os-evaluation-conversion",
        "os-evaluation-reversion",
        "activation",
        "commercial-conversion",
        "deployment-reclassification",
        "term-renewal",
        "operation-reconciliation",
        "deactivation",
    }
)
_ACTIVE_STATES = frozenset({"prepared", "sending", "outcome_unknown", "reconciling", "retry_wait"})


def validate_persisted_operations(
    connection: sqlite3.Connection,
    deployment_public_key: bytes,
    historical_public_keys: frozenset[bytes] = frozenset(),
) -> None:
    del deployment_public_key, historical_public_keys
    rows = connection.execute(
        """SELECT operation_id, operation_type, state, idempotency_key,
        parent_operation_id, request_digest, request_nonce, canonical_request,
        response_content, edition, licensed_product_scope, instance_id, attempt_count,
        next_retry_at_ms, terminal_code, deactivation_reason FROM licensing_operations"""
    ).fetchall()
    active_count = 0
    for row in rows:
        try:
            require_canonical_uuid4(row[0])
            require_canonical_uuid4(row[11])
        except ValidationError as exception:
            raise StateError("Stored licensing operation identity is invalid.") from exception
        operation_type = row[1]
        state = row[2]
        remote = operation_type in _REMOTE_OPERATIONS
        offline = operation_type in {"offline_export", "offline_import"}
        if not remote and not offline:
            raise StateError("Stored licensing operation type is invalid.")
        _validate_identity_fields(row, remote, offline)
        _validate_state(operation_type, state, row[12], row[13], row[14], row[8])
        if state in _ACTIVE_STATES:
            active_count += 1
        if row[8] is not None:
            if not isinstance(row[8], bytes):
                raise StateError("Stored licensing response content is invalid.")
            try:
                parsed = parse_canonical_licensing_document(row[8])
            except ValidationError as exception:
                raise StateError("Stored licensing response content is invalid.") from exception
            if not isinstance(parsed, dict):
                raise StateError("Stored licensing response content is invalid.")
    if active_count > 1:
        raise StateError("Stored licensing operations contain multiple active mutations.")


def _validate_identity_fields(
    row: sqlite3.Row,
    remote: bool,
    offline: bool,
) -> None:
    idempotency_key, parent_id, digest, nonce, request = row[3:8]
    if remote:
        try:
            require_licensing_identifier(idempotency_key, label="Stored idempotency key")
        except ValidationError as exception:
            raise StateError("Stored licensing operation contract is invalid.") from exception
    digest_valid = (
        isinstance(digest, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", digest) is not None
    )
    nonce_valid = remote == (isinstance(nonce, bytes) and len(nonce) == 32)
    parent_valid = (row[1] == "offline_import") == isinstance(parent_id, str)
    reason_valid = (row[1] == "deactivation") == (
        row[15] in {"rehost", "retired", "disaster_recovery", "other"}
    )
    identity_valid = all(
        (
            not offline or idempotency_key is None,
            digest_valid,
            row[9] in {"soai-core", "soai-os"},
            row[10] in {"soai_core", "soai_os", "soai_core_and_os"},
            nonce_valid,
            request is None,
            parent_valid,
            reason_valid,
        )
    )
    if not identity_valid:
        raise StateError("Stored licensing operation contract is invalid.")


def _validate_state(
    operation_type: str | int | float | bytes | None,
    state: str | int | float | bytes | None,
    attempt_count: str | int | float | bytes | None,
    next_retry_at_ms: str | int | float | bytes | None,
    terminal_code: str | int | float | bytes | None,
    response_content: str | int | float | bytes | None,
) -> None:
    state_valid = state in _ACTIVE_STATES | {"succeeded", "failed", "cancelled"}
    attempt_valid = (
        not isinstance(attempt_count, bool)
        and isinstance(attempt_count, int)
        and 0 <= attempt_count <= 1_000_000
    )
    offline_operation = operation_type in {"offline_export", "offline_import"}
    offline_state_valid = not offline_operation or state == "succeeded"
    retry_time_valid = (state in {"retry_wait", "outcome_unknown"}) == isinstance(
        next_retry_at_ms, int
    )
    terminal_code_valid = (state == "failed") == isinstance(terminal_code, str) and (
        terminal_code is None or terminal_code in licensing_operation_terminal_codes()
    )
    response_required = state == "succeeded" and not offline_operation
    response_valid = response_required == isinstance(response_content, bytes)
    if not all(
        (
            state_valid,
            attempt_valid,
            offline_state_valid,
            retry_time_valid,
            terminal_code_valid,
            response_valid,
        )
    ):
        raise StateError("Stored licensing operation state is invalid.")


def validate_persisted_request(
    content: bytes,
    expected_digest: str,
    signature_domain: str,
    deployment_public_key: bytes,
) -> None:
    request = validate_persisted_machine_request(content, expected_digest, signature_domain)
    if request.signing_public_key != deployment_public_key:
        raise StateError("Stored licensing operation signature binding is invalid.")


__all__ = ("validate_persisted_operations", "validate_persisted_request")
