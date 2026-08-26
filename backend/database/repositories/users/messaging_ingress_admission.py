"""SoAI - Atomic Messaging ingress admission [backend/database/repositories/users/messaging_ingress_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError
from core.messaging.control_commands import classify_messaging_control_command
from core.messaging.transport_retention import messaging_event_exceeds_accepted_age
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict
from database.repositories.users.conversation_input_sync_enqueue import (
    sync_enqueue_conversation_input,
)
from database.repositories.users.messaging_binding_admission import (
    ensure_messaging_account_capacity,
    is_messaging_sender_authorized,
    read_messaging_admission_account,
    resolve_messaging_bound_conversation,
)
from database.repositories.users.messaging_control_admission import (
    sync_admit_messaging_control,
)
from database.repositories.users.messaging_delivery_receipts import (
    sync_record_messaging_delivery_receipt,
)
from database.repositories.users.messaging_ingress_records import (
    find_messaging_ingress_replay,
    insert_messaging_ingress_record,
)
from database.repositories.users.messaging_interaction_admission import (
    sync_try_admit_messaging_interaction,
)

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = ("sync_admit_messaging_event",)


def sync_admit_messaging_event(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    account_id: str,
    ingress_id: str,
    input_id: str,
    conversation_id: str,
    event: NormalizedMessagingEvent,
    content_fingerprint: str,
    title: str,
    accepted_at_ms: int,
    storage_root: str | None,
) -> JSONDict:
    existing = find_messaging_ingress_replay(
        conn,
        account_id=account_id,
        provider_event_id=event.provider_event_id,
        content_fingerprint=content_fingerprint,
    )
    if existing is not None:
        return existing
    if messaging_event_exceeds_accepted_age(event, accepted_at_ms):
        return {
            "status": "rejected",
            "outcome": "rejected",
            "diagnostic_code": "provider_event_expired",
        }
    account = read_messaging_admission_account(conn, account_id, event.platform)
    user_id = account[1]
    principal_id = account[4]
    if not isinstance(user_id, int) or not isinstance(principal_id, str):
        raise StateError("Messaging account identity is invalid.")
    if event.provider_principal_id is not None and event.provider_principal_id != principal_id:
        insert_messaging_ingress_record(
            conn,
            ingress_id=ingress_id,
            account_id=account_id,
            user_id=user_id,
            event=event,
            content_fingerprint=content_fingerprint,
            classification="unauthorized",
            outcome="rejected",
            sender_id=None,
            diagnostic_code="principal_mismatch",
            accepted_at_ms=accepted_at_ms,
        )
        return {"status": "rejected", "outcome": "rejected", "ingress_id": ingress_id}
    if event.classification != "prompt":
        receipt_updated = False
        if (
            event.classification == "protocol"
            and event.receipt_status is not None
            and event.provider_message_id is not None
        ):
            receipt_updated = sync_record_messaging_delivery_receipt(
                conn,
                account_id=account_id,
                provider_message_id=event.provider_message_id,
                receipt_status=event.receipt_status,
                receipt_at_ms=event.provider_timestamp_ms or accepted_at_ms,
            )
        insert_messaging_ingress_record(
            conn,
            ingress_id=ingress_id,
            account_id=account_id,
            user_id=user_id,
            event=event,
            content_fingerprint=content_fingerprint,
            classification=event.classification,
            outcome="ignored",
            sender_id=None,
            diagnostic_code=(
                f"receipt_{event.receipt_status}"
                if event.receipt_status is not None
                else event.classification
            ),
            accepted_at_ms=accepted_at_ms,
        )
        return {
            "status": "ignored",
            "outcome": "ignored",
            "ingress_id": ingress_id,
            "receipt_updated": receipt_updated,
        }
    sender_id = event.sender_id
    if sender_id is None or not is_messaging_sender_authorized(
        conn,
        account_id=account_id,
        user_id=user_id,
        sender_id=sender_id,
        accept_messages_from_anyone=account[11] == 1,
    ):
        insert_messaging_ingress_record(
            conn,
            ingress_id=ingress_id,
            account_id=account_id,
            user_id=user_id,
            event=event,
            content_fingerprint=content_fingerprint,
            classification="unauthorized",
            outcome="rejected",
            sender_id=None,
            diagnostic_code="sender_unauthorized",
            accepted_at_ms=accepted_at_ms,
        )
        return {"status": "rejected", "outcome": "rejected", "ingress_id": ingress_id}
    model_settings = parse_json_dict(
        account[5],
        field="Messaging account model settings",
    )
    command = classify_messaging_control_command(
        event,
        verified_principal_label=(account[8] if isinstance(account[8], str) else None),
    )
    if command in {"new", "cancel"}:
        locale = account[9]
        if not isinstance(locale, str) or not isinstance(account[3], str):
            raise StateError("Messaging account control configuration is invalid.")
        if not isinstance(account[7], int):
            raise StateError("Messaging account lifecycle generation is invalid.")
        return sync_admit_messaging_control(
            conn,
            account_id=account_id,
            user_id=user_id,
            account_label=account[3],
            account_generation=account[7],
            locale=locale,
            model_settings=model_settings,
            ingress_id=ingress_id,
            conversation_id=conversation_id,
            command=command,
            event=event,
            content_fingerprint=content_fingerprint,
            title=title,
            accepted_at_ms=accepted_at_ms,
        )
    interaction_result = sync_try_admit_messaging_interaction(
        conn,
        fernets,
        ingress_id=ingress_id,
        account_id=account_id,
        user_id=user_id,
        account_generation=account[7],
        platform=event.platform,
        locale=account[9],
        plaintext_secret_replies_enabled=account[10] == 1,
        event=event,
        content_fingerprint=content_fingerprint,
        accepted_at_ms=accepted_at_ms,
    )
    if interaction_result is not None:
        return interaction_result
    if command is not None:
        locale = account[9]
        if not isinstance(locale, str) or not isinstance(account[3], str):
            raise StateError("Messaging account control configuration is invalid.")
        if not isinstance(account[7], int):
            raise StateError("Messaging account lifecycle generation is invalid.")
        return sync_admit_messaging_control(
            conn,
            account_id=account_id,
            user_id=user_id,
            account_label=account[3],
            account_generation=account[7],
            locale=locale,
            model_settings=model_settings,
            ingress_id=ingress_id,
            conversation_id=conversation_id,
            command=command,
            event=event,
            content_fingerprint=content_fingerprint,
            title=title,
            accepted_at_ms=accepted_at_ms,
        )
    ensure_messaging_account_capacity(conn, account_id)
    conv_id, binding_generation, input_generation = resolve_messaging_bound_conversation(
        conn,
        account_id=account_id,
        user_id=user_id,
        account_label=str(account[3]),
        model_settings=model_settings,
        event=event,
        title=title,
        conv_id=conversation_id,
        accepted_at_ms=accepted_at_ms,
    )
    insert_messaging_ingress_record(
        conn,
        ingress_id=ingress_id,
        account_id=account_id,
        user_id=user_id,
        event=event,
        content_fingerprint=content_fingerprint,
        classification="prompt",
        outcome="accepted",
        sender_id=sender_id,
        diagnostic_code=None,
        accepted_at_ms=accepted_at_ms,
    )
    source_metadata = event.source_metadata()
    source_metadata["account_id"] = account_id
    source_metadata["account_generation"] = account[7]
    source_metadata["binding_generation"] = binding_generation
    input_record = sync_enqueue_conversation_input(
        conn,
        conv_id,
        user_id,
        "prompt",
        "messaging",
        event.text,
        None,
        "[]",
        serialize_json_compact_stable(model_settings),
        ingress_id,
        None,
        None,
        ingress_id,
        serialize_json_compact_stable(source_metadata),
        serialize_json_compact_stable([descriptor.to_payload() for descriptor in event.media]),
        input_id,
        accepted_at_ms,
        input_generation,
        storage_root,
    )
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET linked_input_id = ?, result_conv_id = ?,
            account_generation = ?, binding_generation = ?
        WHERE ingress_id = ?
        """,
        (input_id, conv_id, account[7], binding_generation, ingress_id),
    )
    return {
        "status": "accepted",
        "outcome": "accepted",
        "ingress_id": ingress_id,
        "input_id": input_record["input_id"],
        "conv_id": conv_id,
        "user_id": user_id,
        "conversation_created": conv_id == conversation_id,
    }
