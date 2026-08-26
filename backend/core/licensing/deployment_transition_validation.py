"""SoAI - Deployment rehost lineage validation [backend/core/licensing/deployment_transition_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hmac
import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.licensing.deployment_transition import (
    DeploymentRehostTransition,
    validate_deployment_rehost_transition,
)
from core.licensing.entitlement_validation import EntitlementBinding, validate_entitlement
from core.licensing.machine_request_validation import (
    validate_deactivation_request,
    validate_persisted_machine_request,
)
from core.licensing.trust import IssuerAuthorizationCatalog
from core.licensing.types import Edition


def validate_deployment_transition_lineage(
    connection: sqlite3.Connection,
    *,
    catalog: IssuerAuthorizationCatalog | None,
    edition: Edition,
    instance_id: str,
    current_public_key: bytes,
    current_key_created_at_ms: int,
) -> frozenset[bytes]:
    rows = connection.execute("""SELECT operation_id, instance_id, deployment_id, old_public_key,
        new_public_key, canonical_transition, completed_at_ms
        FROM licensing_deployment_transitions ORDER BY completed_at_ms, operation_id""").fetchall()
    if not rows:
        return frozenset()
    if catalog is None:
        raise StateError("Deployment transition validation requires release trust material.")
    transitions = [
        _validate_transition_row(
            connection,
            row,
            catalog=catalog,
            edition=edition,
            expected_instance_id=instance_id,
        )
        for row in rows
    ]
    for previous, current in zip(transitions, transitions[1:], strict=False):
        if previous.completed_at_ms >= current.completed_at_ms or not hmac.compare_digest(
            previous.new_public_key, current.old_public_key
        ):
            raise StateError("Deployment rehost transitions do not form one ordered lineage.")
    final_transition = transitions[-1]
    if not hmac.compare_digest(final_transition.new_public_key, current_public_key) or (
        final_transition.completed_at_ms != current_key_created_at_ms
    ):
        raise StateError("Deployment rehost lineage does not end at the current identity.")
    return frozenset(transition.old_public_key for transition in transitions)


def _validate_transition_row(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    catalog: IssuerAuthorizationCatalog,
    edition: Edition,
    expected_instance_id: str,
) -> DeploymentRehostTransition:
    if not isinstance(row[5], bytes):
        raise StateError("Stored deployment rehost transition is invalid.")
    try:
        transition = validate_deployment_rehost_transition(bytes(row[5]))
    except ValidationError as exception:
        raise StateError("Stored deployment rehost transition is invalid.") from exception
    metadata_matches = (row[0], row[1], row[2], row[6]) == (
        transition.operation_id,
        transition.instance_id,
        transition.deployment_id,
        transition.completed_at_ms,
    )
    keys_match = (
        isinstance(row[3], bytes)
        and isinstance(row[4], bytes)
        and hmac.compare_digest(bytes(row[3]), transition.old_public_key)
        and hmac.compare_digest(bytes(row[4]), transition.new_public_key)
    )
    if not metadata_matches or not keys_match or transition.instance_id != expected_instance_id:
        raise StateError("Stored deployment rehost transition metadata is invalid.")
    _validate_transition_operation(connection, transition)
    _validate_historical_entitlement(
        connection,
        transition,
        catalog=catalog,
        edition=edition,
    )
    return transition


def _validate_transition_operation(
    connection: sqlite3.Connection,
    transition: DeploymentRehostTransition,
) -> None:
    operation = connection.execute(
        """SELECT operation_type, state, request_digest, canonical_request,
        instance_id, deployment_id, updated_at_ms, idempotency_key, activation_id
        FROM licensing_operations
        WHERE operation_id = ?""",
        (transition.operation_id,),
    ).fetchone()
    if operation is None:
        raise StateError("Deployment rehost operation binding is invalid.")
    operation_metadata = (operation[0], operation[1], operation[4], operation[5], operation[6])
    expected_metadata = (
        "deactivation",
        "succeeded",
        transition.instance_id,
        transition.deployment_id,
        transition.completed_at_ms,
    )
    if (
        operation_metadata != expected_metadata
        or not isinstance(operation[2], str)
        or not isinstance(operation[3], bytes)
    ):
        raise StateError("Deployment rehost operation binding is invalid.")
    machine_request = validate_persisted_machine_request(
        bytes(operation[3]),
        str(operation[2]),
        "soai-licensing-deactivation-request-v1",
    )
    request = validate_deactivation_request(machine_request)
    request_metadata = (
        request.reason,
        operation[7],
        operation[8],
        request.instance_id,
        request.deployment_id,
    )
    expected_request_metadata = (
        "rehost",
        request.idempotency_key,
        request.activation_id,
        transition.instance_id,
        transition.deployment_id,
    )
    if request_metadata != expected_request_metadata or not hmac.compare_digest(
        request.deployment_public_key, transition.old_public_key
    ):
        raise StateError("Deployment rehost request does not match its transition.")


def _validate_historical_entitlement(
    connection: sqlite3.Connection,
    transition: DeploymentRehostTransition,
    *,
    catalog: IssuerAuthorizationCatalog,
    edition: Edition,
) -> None:
    row = connection.execute(
        """SELECT canonical_content, generation, issuer_authorization_snapshot
        FROM licensing_documents WHERE disposition = 'historical'
        AND document_type = 'entitlement' AND deployment_id = ?
        ORDER BY generation DESC LIMIT 1""",
        (transition.deployment_id,),
    ).fetchone()
    if (
        row is None
        or not isinstance(row[0], bytes)
        or isinstance(row[1], bool)
        or not isinstance(row[1], int)
        or not isinstance(row[2], bytes)
    ):
        raise StateError("Deployment rehost transition has no historical entitlement anchor.")
    try:
        validated = validate_entitlement(
            bytes(row[0]),
            catalog,
            EntitlementBinding(
                edition=edition,
                instance_id=transition.instance_id,
                deployment_public_key=transition.old_public_key,
                current_deployment_id=transition.deployment_id,
                current_generation=int(row[1]),
                current_document=bytes(row[0]),
            ),
            bytes(row[2]),
        )
    except ValidationError as exception:
        raise StateError("Deployment rehost entitlement anchor is invalid.") from exception
    if validated.deployment_id != transition.deployment_id or validated.generation != row[1]:
        raise StateError("Deployment rehost entitlement anchor metadata is invalid.")


__all__ = ("validate_deployment_transition_lineage",)
