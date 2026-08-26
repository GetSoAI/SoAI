"""SoAI - Mail SMTP transport helpers [backend/features/mail/smtp_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import smtplib
import socket
import ssl
from email.message import EmailMessage
from typing import TYPE_CHECKING, override

from core.errors.exceptions import ValidationError
from features.mail.auth_payload_fields import extract_mail_auth_payload_fields

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "send_smtp_message_sync",
    "test_smtp_transport_sync",
)


class _SoAISmtp(smtplib.SMTP):
    _host: str
    __slots__ = ("_soai_tls_server_hostname",)

    def __init__(
        self,
        *,
        connect_host: str,
        server_hostname: str,
        port: int,
        timeout: float,
    ) -> None:
        self._soai_tls_server_hostname = server_hostname
        self._host = connect_host
        super().__init__(host=connect_host, port=port, timeout=timeout)

    @override
    def starttls(self, *, context: ssl.SSLContext | None = None) -> tuple[int, bytes]:
        previous_host = self._host
        self._host = self._soai_tls_server_hostname
        try:
            return super().starttls(context=context)
        finally:
            self._host = previous_host


class _SoAISmtpSSL(smtplib.SMTP_SSL):
    __slots__ = ("_soai_ssl_context", "_soai_tls_server_hostname")

    def __init__(
        self,
        *,
        connect_host: str,
        server_hostname: str,
        port: int,
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        self._soai_ssl_context = context
        self._soai_tls_server_hostname = server_hostname
        super().__init__(host=connect_host, port=port, timeout=timeout, context=context)

    def _get_socket(self, host: str, port: int, timeout: float) -> ssl.SSLSocket:
        sock = socket.create_connection((host, port), timeout)
        return self._soai_ssl_context.wrap_socket(
            sock,
            server_hostname=self._soai_tls_server_hostname,
        )


def test_smtp_transport_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> JSONDict:
    with _open_smtp_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        code, response = connection.noop()
    return {"status": "ok", "smtp_code": int(code), "smtp_response": _decode_response(response)}


def send_smtp_message_sync(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    message: EmailMessage,
    connect_timeout_sec: float,
    connect_host: str,
) -> JSONDict:
    recipients = message.get_all("To", []) + message.get_all("Cc", []) + message.get_all("Bcc", [])
    envelope = [item for item in recipients if isinstance(item, str) and item.strip()]
    if not envelope:
        raise ValidationError("Outgoing message requires at least one envelope recipient.")
    with _open_smtp_connection(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        refused = connection.send_message(message)
        if refused:
            raise ValidationError("SMTP server refused one or more recipients.")
    return {"ok": True, "refused_recipients": []}


def _open_smtp_connection(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> smtplib.SMTP:
    timeout = max(float(connect_timeout_sec), 1.0)
    context = ssl.create_default_context()
    if runtime_state.smtp_security == "tls":
        connection: smtplib.SMTP = _SoAISmtpSSL(
            connect_host=connect_host,
            server_hostname=runtime_state.smtp_host,
            port=runtime_state.smtp_port,
            timeout=timeout,
            context=context,
        )
    elif runtime_state.smtp_security == "starttls":
        connection = _SoAISmtp(
            connect_host=connect_host,
            server_hostname=runtime_state.smtp_host,
            port=runtime_state.smtp_port,
            timeout=timeout,
        )
        connection.ehlo_or_helo_if_needed()
        connection.starttls(context=context)
    else:
        raise ValidationError("smtp_security must be tls or starttls.")
    connection.ehlo_or_helo_if_needed()
    _smtp_authenticate(connection=connection, auth_payload=auth_payload)
    return connection


def _smtp_authenticate(*, connection: smtplib.SMTP, auth_payload: JSONDict) -> None:
    auth_type, username, password, sasl = extract_mail_auth_payload_fields(auth_payload)
    if auth_type == "password":
        connection.login(username, password)
        return
    if auth_type == "oauth2":
        if not sasl:
            raise ValidationError("SMTP XOAUTH2 SASL payload is required.")
        code, response = connection.docmd("AUTH", f"XOAUTH2 {sasl}")
        if int(code) >= 400:
            raise ValidationError(
                f"SMTP XOAUTH2 authentication failed: {int(code)} {_decode_response(response)}",
            )
        return
    raise ValidationError("SMTP auth_type is invalid.")


def _decode_response(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
