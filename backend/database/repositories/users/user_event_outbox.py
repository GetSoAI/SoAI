"""SoAI - User domain event outbox helpers [backend/database/repositories/users/user_event_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.users.user_id import is_strict_user_id
from core.users.username import require_canonical_username
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload

__all__ = ("sync_enqueue_user_domain_event",)


def sync_enqueue_user_domain_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    created_at_ms: int,
    user_id: int,
    username: str,
    is_admin: bool | None = None,
    identity_revision: int | None = None,
    operation_id: str | None = None,
    actor_user_id: int | None = None,
    previous_username: str | None = None,
    password_revision: int | None = None,
    revoked_session_jtis: tuple[str, ...] | None = None,
    rotation_source_jti: str | None = None,
    invalidation_reason: str | None = None,
    session_jtis: tuple[str, ...] | None = None,
) -> None:
    if not _is_supported_user_event_type(event_type):
        raise StateError(f"Unsupported user domain event type: {event_type}")
    if not is_strict_user_id(user_id):
        raise StateError("User domain events require user_id to be a positive integer.")
    try:
        normalized_username = require_canonical_username(username)
    except ValidationError as exception:
        raise StateError("User domain events require a canonical username.") from exception
    if username != normalized_username:
        raise StateError("User domain events require a canonical username.")
    payload = build_domain_event_payload(
        fields={
            "user_id": int(user_id),
            "username": normalized_username,
        },
    )
    if _is_user_role_event_type(event_type):
        if is_admin is None or identity_revision is None:
            raise StateError(f"User domain event '{event_type}' requires identity fields.")
        payload["is_admin"] = bool(is_admin)
        payload["identity_revision"] = identity_revision
    if event_type == "UserSessionInvalidatedEvent":
        if not invalidation_reason or session_jtis is None:
            raise StateError("Session invalidation events require exact session details.")
        payload["reason"] = invalidation_reason
        payload["session_jtis"] = list(session_jtis)
    elif event_type in {"UserPasswordChangedEvent", "UserUsernameChangedEvent"}:
        if revoked_session_jtis is None or operation_id is None or actor_user_id is None:
            raise StateError("Password change events require session invalidation semantics.")
        invalid_jtis = any(
            not isinstance(jti, str) or not jti or jti != jti.strip()
            for jti in revoked_session_jtis
        )
        if invalid_jtis or len(set(revoked_session_jtis)) != len(revoked_session_jtis):
            raise StateError("Password change events require unique non-empty session JTIs.")
        payload["revoked_session_jtis"] = list(revoked_session_jtis)
        payload["operation_id"] = operation_id
        payload["actor_user_id"] = actor_user_id
        payload["rotation_source_jti"] = rotation_source_jti
        if rotation_source_jti is not None and rotation_source_jti not in revoked_session_jtis:
            raise StateError("Rotation source must be one of the revoked sessions.")
        if event_type == "UserPasswordChangedEvent":
            if password_revision is None:
                raise StateError("Password change event requires password_revision.")
            payload["password_revision"] = password_revision
        else:
            if previous_username is None or identity_revision is None:
                raise StateError("Username change event requires identity fields.")
            payload["previous_username"] = previous_username
            payload["identity_revision"] = identity_revision
    elif any(
        value is not None
        for value in (
            revoked_session_jtis,
            rotation_source_jti,
            operation_id,
            actor_user_id,
            previous_username,
            password_revision,
            invalidation_reason,
            session_jtis,
        )
    ):
        raise StateError("Mutation correlation is invalid for this user event.")
    sync_enqueue_domain_event_payload(
        conn,
        event_type=event_type,
        payload=payload,
        created_at_ms=created_at_ms,
    )


def _is_user_role_event_type(event_type: str) -> bool:
    return event_type in {"UserCreatedEvent", "UserRoleChangedEvent"}


def _is_supported_user_event_type(event_type: str) -> bool:
    if _is_user_role_event_type(event_type):
        return True
    return event_type in {
        "UserDeletedEvent",
        "UserPasswordChangedEvent",
        "UserUsernameChangedEvent",
        "UserSessionInvalidatedEvent",
    }
