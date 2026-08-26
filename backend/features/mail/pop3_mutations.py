"""SoAI - Mail POP3 mutation helpers [backend/features/mail/pop3_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from contextlib import closing
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.mail.pop3_session import open_pop3_connection

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.internal_protocols import POP3ConnectionProtocol
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = ("delete_pop3_message_sync",)


def delete_pop3_message_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    uidl: str,
) -> None:
    with closing(
        open_pop3_connection(
            runtime_state=runtime_state,
            auth_payload=auth_payload,
            connect_timeout_sec=connect_timeout_sec,
            connect_host=connect_host,
        ),
    ) as connection:
        message_number = _resolve_message_number(connection, uidl=uidl)
        response = connection.dele(message_number)
        if not isinstance(response, bytes) or not response.startswith(b"+OK"):
            raise ValidationError("POP3 DELE failed.")
        quit_response = connection.quit()
        if not isinstance(quit_response, bytes) or not quit_response.startswith(b"+OK"):
            raise ValidationError("POP3 delete commit failed.")


def _resolve_message_number(connection: POP3ConnectionProtocol, *, uidl: str) -> int:
    response, lines, _octets = connection.uidl()
    if not isinstance(response, bytes) or not response.startswith(b"+OK"):
        raise ValidationError("POP3 UIDL failed.")
    for line in lines:
        if not isinstance(line, bytes):
            continue
        parts = line.decode("utf-8", errors="replace").split(" ", 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        if parts[1].strip() == uidl:
            return int(parts[0])
    raise ValidationError("POP3 message could not be resolved from UIDL.")
