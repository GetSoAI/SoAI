"""SoAI - Calendar iMIP delivery helpers [backend/features/calendar/calendar_imip_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from functools import partial
from typing import TYPE_CHECKING

from icalendar import Calendar

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.calendar.calendar_ics import build_calendar_event_ics
from features.calendar.internal_protocols import LinkedMailAccountLockProviderProtocol
from features.external_accounts.external_account_fields import (
    require_external_account_username,
)
from features.mail.auth_payload_fields import require_mail_auth_payload_username
from features.mail.outgoing_addresses import resolve_message_id_domain
from features.mail.runtime_state import load_mail_account_runtime
from features.mail.smtp_transport import send_smtp_message_sync
from features.mail.transport_context import prepare_mail_transport_context

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.mail.protocols import DatabaseMailProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = (
    "PreparedCalendarInviteReply",
    "prepare_calendar_invite_reply_prerequisites",
    "resolve_calendar_invite_attendee_email",
    "send_calendar_invite_reply",
)


@dataclass(frozen=True, slots=True)
class PreparedCalendarInviteReply:
    prepared_mail: PreparedMailTransportContext
    sender_email: str
    organizer_email: str


async def prepare_calendar_invite_reply_prerequisites(
    *,
    database_mail: DatabaseMailProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    mail_account_locks: LinkedMailAccountLockProviderProtocol,
    user_id: int,
    mail_account_id: str,
    organizer: JSONDict,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> PreparedCalendarInviteReply:
    async with mail_account_locks.mail_account_lock(user_id=user_id, account_id=mail_account_id):
        prepared, sender_email, organizer_email = await _prepare_invite_reply_transport(
            config=config,
            runtime_flags=runtime_flags,
            database_mail=database_mail,
            external_accounts=external_accounts,
            user_id=user_id,
            mail_account_id=mail_account_id,
            organizer=organizer,
        )
    return PreparedCalendarInviteReply(
        prepared_mail=prepared,
        sender_email=sender_email,
        organizer_email=organizer_email,
    )


async def resolve_calendar_invite_attendee_email(
    *,
    database_mail: DatabaseMailProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    mail_account_locks: LinkedMailAccountLockProviderProtocol,
    user_id: int,
    mail_account_id: str,
) -> str:
    async with mail_account_locks.mail_account_lock(user_id=user_id, account_id=mail_account_id):
        runtime_state = await load_mail_account_runtime(
            database_mail=database_mail,
            external_accounts=external_accounts,
            user_id=user_id,
            account_id=mail_account_id,
            decrypt_secrets=False,
        )
    return require_external_account_username(
        runtime_state.external_account,
        build_error=ValidationError,
    )


async def send_calendar_invite_reply(
    *,
    config: ConfigProtocol,
    mail_blocking_pool: BoundedBlockingPool,
    prepared_reply: PreparedCalendarInviteReply,
    event_payload: JSONDict,
    response_action: str,
    comment: str | None,
) -> None:
    raw_ics, _event_uid = build_calendar_event_ics(
        event_payload=event_payload,
        uid=coerce_optional_trimmed_str(event_payload.get("uid")),
    )
    reply_ics = _build_reply_ics(raw_ics)
    message = EmailMessage()
    message["Message-ID"] = make_msgid(
        domain=resolve_message_id_domain(prepared_reply.sender_email),
    )
    message["Date"] = formatdate(localtime=False)
    message["From"] = formataddr(("", prepared_reply.sender_email))
    message["To"] = formataddr(("", prepared_reply.organizer_email))
    message["Subject"] = f"Re: {_resolve_summary(event_payload)}"
    message.set_content(_build_reply_text(event_payload, response_action, comment))
    message.add_alternative(
        reply_ics,
        subtype="calendar",
        charset="utf-8",
        params={"method": "REPLY"},
    )
    prepared_mail = prepared_reply.prepared_mail
    timeout_sec = prepared_mail.connect_timeout_sec + float(
        config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC"),
    )
    await run_bounded_blocking_call(
        mail_blocking_pool,
        partial(
            send_smtp_message_sync,
            runtime_state=prepared_mail.runtime_state,
            auth_payload=prepared_mail.auth_payload,
            message=message,
            connect_timeout_sec=prepared_mail.connect_timeout_sec,
            connect_host=prepared_mail.smtp_connect_host,
        ),
        timeout_sec=timeout_sec,
    )


def _build_reply_ics(raw_ics: str) -> str:
    calendar = Calendar.from_ical(raw_ics)
    calendar.add("method", "REPLY")
    return calendar.to_ical().decode("utf-8")


def _build_reply_text(
    event_payload: JSONDict,
    response_action: str,
    comment: str | None,
) -> str:
    status_map = {
        "accept": "accepted",
        "tentative": "marked tentative for",
        "decline": "declined",
    }
    action_text = status_map.get(response_action, response_action)
    summary = _resolve_summary(event_payload)
    if isinstance(comment, str) and comment.strip():
        return f"I have {action_text} the invitation for {summary}.\n\nComment: {comment.strip()}"
    return f"I have {action_text} the invitation for {summary}."


def _resolve_summary(event_payload: JSONDict) -> str:
    summary_value = event_payload.get("summary")
    if isinstance(summary_value, str) and summary_value.strip():
        return summary_value.strip()
    return "(no title)"


def _require_email(address: JSONDict, message: str) -> str:
    email_value = address.get("email")
    email = email_value.strip() if isinstance(email_value, str) else ""
    if not email:
        raise ValidationError(message)
    return email


async def _prepare_invite_reply_transport(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    database_mail: DatabaseMailProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    mail_account_id: str,
    organizer: JSONDict,
) -> tuple[PreparedMailTransportContext, str, str]:
    organizer_email = _require_email(organizer, "Calendar organizer email is required.")
    prepared = await prepare_mail_transport_context(
        config=config,
        runtime_flags=runtime_flags,
        database_mail=database_mail,
        external_accounts=external_accounts,
        user_id=user_id,
        account_id=mail_account_id,
    )
    sender_email = require_mail_auth_payload_username(prepared.auth_payload)
    return prepared, sender_email, organizer_email
