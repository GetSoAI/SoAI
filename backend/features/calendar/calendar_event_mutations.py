"""SoAI - Calendar event mutation orchestration [backend/features/calendar/calendar_event_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.calendar.calendar_event_support import (
    load_existing_event,
    merge_event_payload,
    require_action,
    require_event_payload,
    require_id,
    update_invite_attendees,
)
from features.calendar.calendar_imip_delivery import (
    PreparedCalendarInviteReply,
    prepare_calendar_invite_reply_prerequisites,
    resolve_calendar_invite_attendee_email,
    send_calendar_invite_reply,
)
from features.calendar.calendar_record_context import (
    load_calendar_row,
    load_event_row,
    require_calendar_account_id_from_row,
    require_event_calendar_id,
)
from features.calendar.calendar_remote_mutations import (
    delete_calendar_event,
    put_calendar_event,
)
from features.calendar.calendar_sync_notifications import (
    create_calendar_invite_update_notification,
    resolve_calendar_account_label,
    resolve_calendar_event_start,
    resolve_calendar_event_summary,
)
from features.calendar.calendar_transport_preparation import (
    prepare_service_calendar_transport_context,
)
from features.calendar.formatting import format_calendar_event
from features.calendar.internal_protocols import CalendarMutationServiceProtocol

__all__ = (
    "respond_to_calendar_invite",
    "update_calendar_event",
)

OPERATION = "features.calendar.calendar_event_mutations"
LOGGER_NAME = "SoAI.features.calendar.calendar_event_mutations"


async def update_calendar_event(
    service: CalendarMutationServiceProtocol,
    *,
    user_id: int,
    payload: JSONDict,
) -> JSONDict:
    action = require_action(payload.get("action"), {"create", "update", "delete"})
    calendar_id = require_id(payload.get("calendar_id"), "calendar_id is required.")
    calendar_row = await load_calendar_row(
        service.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    if calendar_row.get("read_only") is True:
        raise ValidationError("Calendar is read-only.")
    if service.runtime_flags.offline_mode:
        raise ValidationError(
            "Calendar event mutations are unavailable while offline mode is enabled.",
        )
    account_id = require_calendar_account_id_from_row(calendar_row)
    prepared = await prepare_service_calendar_transport_context(
        service,
        user_id=user_id,
        account_id=account_id,
    )
    if action == "delete":
        return await delete_calendar_event(
            database_calendar=service.database_calendar,
            http_client=service.http_client,
            prepared=prepared,
            user_id=user_id,
            calendar_id=calendar_id,
            payload=payload,
        )
    event_patch = require_event_payload(payload.get("event"))
    existing_event = await load_existing_event(
        database_calendar=service.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        action=action,
        payload=payload,
    )
    mutation_payload = merge_event_payload(existing_event, event_patch)
    mutation_payload["calendar_id"] = calendar_id
    stored_event, warnings = await put_calendar_event(
        database_calendar=service.database_calendar,
        http_client=service.http_client,
        prepared=prepared,
        user_id=user_id,
        calendar_row=calendar_row,
        account_id=account_id,
        existing_event=existing_event,
        event_payload=mutation_payload,
    )
    response: JSONDict = {
        "event": format_calendar_event(stored_event),
        "supported_actions": ["update", "delete", "respond"],
    }
    if warnings:
        response["warnings"] = warnings
    return response


async def respond_to_calendar_invite(
    service: CalendarMutationServiceProtocol,
    *,
    user_id: int,
    event_id: str,
    action: str,
    comment: str | None,
) -> JSONDict:
    response_action = require_action(action, {"accept", "tentative", "decline"})
    if service.runtime_flags.offline_mode:
        raise ValidationError(
            "Calendar invite responses are unavailable while offline mode is enabled.",
        )
    event_row = await load_event_row(
        service.database_calendar,
        user_id=user_id,
        event_id=event_id,
    )
    calendar_id = require_event_calendar_id(event_row)
    calendar_row = await load_calendar_row(
        service.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    if calendar_row.get("read_only") is True:
        raise ValidationError("Calendar is read-only.")
    account_id = require_calendar_account_id_from_row(calendar_row)
    prepared = await prepare_service_calendar_transport_context(
        service,
        user_id=user_id,
        account_id=account_id,
    )
    prepared_invite_reply: PreparedCalendarInviteReply | None = None
    event_payload = merge_event_payload(
        event_row,
        {"attendees": []},
    )
    organizer_value = event_payload.get("organizer")
    organizer = organizer_value if isinstance(organizer_value, dict) else None
    attendee_email = prepared.account_username
    linked_mail_account_id = prepared.runtime_state.linked_mail_account_id
    if linked_mail_account_id is not None and organizer is None:
        attendee_email = await resolve_calendar_invite_attendee_email(
            database_mail=service.database_mail,
            external_accounts=service.external_accounts,
            mail_account_locks=service,
            user_id=user_id,
            mail_account_id=linked_mail_account_id,
        )
    if organizer is not None:
        if linked_mail_account_id is None:
            raise ValidationError(
                "A linked mail account is required to send calendar invite responses.",
            )
        prepared_invite_reply = await prepare_calendar_invite_reply_prerequisites(
            database_mail=service.database_mail,
            external_accounts=service.external_accounts,
            mail_account_locks=service,
            user_id=user_id,
            mail_account_id=linked_mail_account_id,
            organizer=organizer,
            config=service.config,
            runtime_flags=service.runtime_flags,
        )
        attendee_email = prepared_invite_reply.sender_email
    event_payload = merge_event_payload(
        event_row,
        {"attendees": update_invite_attendees(event_row, attendee_email, response_action)},
    )
    stored_event, warnings = await put_calendar_event(
        database_calendar=service.database_calendar,
        http_client=service.http_client,
        prepared=prepared,
        user_id=user_id,
        calendar_row=calendar_row,
        account_id=account_id,
        existing_event=event_row,
        event_payload=event_payload,
    )
    if organizer is not None and prepared_invite_reply is not None:
        try:
            await send_calendar_invite_reply(
                config=service.config,
                mail_blocking_pool=service.mail_blocking_pool,
                prepared_reply=prepared_invite_reply,
                event_payload=event_payload,
                response_action=response_action,
                comment=comment,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                _calendar_event_mutations_logger(),
                exception,
                message="Failed to send calendar invite reply email after saving response.",
                operation=OPERATION,
                level="warning",
                details={"user_id": user_id, "event_id": event_id},
            )
            warning_reason = project_public_exception(exception).message
            warnings.append(
                f"Calendar invite response was saved, but SoAI could not send the organizer reply email: {warning_reason}",
            )
    try:
        await create_calendar_invite_update_notification(
            database_notifications=service.database_notifications,
            user_id=user_id,
            account_label=resolve_calendar_account_label(
                prepared.runtime_state.account,
                prepared.runtime_state.external_account,
            ),
            summary=resolve_calendar_event_summary(stored_event),
            start=resolve_calendar_event_start(stored_event),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            _calendar_event_mutations_logger(),
            exception,
            message="Failed to create local invite update notification after response save.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "event_id": event_id},
        )
        warning_reason = project_public_exception(exception).message
        warnings.append(
            f"Calendar invite response was saved, but SoAI could not create the local update notification: {warning_reason}",
        )
    response: JSONDict = {
        "ok": True,
        "action": response_action,
        "comment": comment,
        "event": format_calendar_event(stored_event),
    }
    if warnings:
        response["warnings"] = warnings
    return response


def _calendar_event_mutations_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
