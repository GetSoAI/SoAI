"""SoAI - Mail POP3 message fetching [backend/features/mail/pop3_message_fetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.datetime_conversion import datetime_to_epoch_ms
from features.mail.message_parsing import parse_message_bytes
from features.mail.pop3_session import open_pop3_uidl_listing_context

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.internal_protocols import POP3ConnectionProtocol
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "fetch_pop3_message_bytes_sync",
    "fetch_pop3_payload",
)

_POP3_INBOX = "INBOX"


def fetch_pop3_message_bytes_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    uidl: str,
) -> bytes:
    with open_pop3_uidl_listing_context(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as listing:
        for message_number, message_uidl in listing.entries:
            if message_uidl != uidl:
                continue
            return _retr_message_bytes(
                connection=listing.connection,
                message_number=message_number,
            )
    raise ValidationError("POP3 message could not be resolved from UIDL.")


def fetch_pop3_payload(
    *,
    connection: POP3ConnectionProtocol,
    runtime_state: MailAccountRuntimeState,
    message_number: int,
    uidl: str,
    snippet_max_chars: int,
) -> JSONDict:
    message_bytes = _retr_message_bytes(connection=connection, message_number=message_number)
    return parse_message_bytes(
        message_bytes=message_bytes,
        remote_mailbox=_POP3_INBOX,
        uidvalidity=None,
        uid=None,
        uidl=uidl,
        received_at_ms=_extract_received_at_ms(message_bytes),
        unread=False,
        flagged=False,
        attachment_identity_key=f"pop3:{runtime_state.account_id}:{uidl}",
        snippet_max_chars=snippet_max_chars,
    )


def _retr_message_bytes(*, connection: POP3ConnectionProtocol, message_number: int) -> bytes:
    response, lines, _octets = connection.retr(message_number)
    if not isinstance(response, bytes) or not response.startswith(b"+OK"):
        raise ValidationError("POP3 RETR failed.")
    return b"\r\n".join(lines)


def _extract_received_at_ms(message_bytes: bytes) -> int:
    message = BytesParser(policy=policy.default).parsebytes(message_bytes)
    header_value = message.get("Date")
    if not isinstance(header_value, str) or not header_value.strip():
        return 0
    parsed = parsedate_to_datetime(header_value)
    return datetime_to_epoch_ms(parsed)
