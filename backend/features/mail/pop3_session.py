"""SoAI - Mail POP3 session helpers [backend/features/mail/pop3_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import poplib
import socket
import ssl
from collections.abc import Generator
from contextlib import AbstractContextManager, closing, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.errors.exceptions import ValidationError
from features.mail.auth_payload_fields import extract_mail_auth_payload_fields
from features.mail.internal_protocols import POP3ConnectionProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "list_pop3_uidls",
    "open_pop3_connection",
    "open_pop3_connection_context",
    "open_pop3_uidl_listing_context",
)


@dataclass(frozen=True, slots=True)
class POP3UidlListing:
    connection: POP3ConnectionProtocol
    entries: list[tuple[int, str]]


class _OAuthPOP3(poplib.POP3):
    _tls_server_hostname: str
    sock: socket.socket

    def __init__(
        self,
        host: str,
        port: int = poplib.POP3_PORT,
        timeout: float = 60.0,
        *,
        tls_server_hostname: str,
    ) -> None:
        self._tls_server_hostname = tls_server_hostname
        super().__init__(host=host, port=port, timeout=timeout)

    def authenticate_xoauth2(self, sasl: str) -> bytes:
        auth_command = f"AUTH XOAUTH2 {sasl}\r\n".encode()
        self.sock.sendall(auth_command)
        response_reader = self.sock.makefile("rb")
        try:
            response = response_reader.readline()
        finally:
            response_reader.close()
        if not isinstance(response, bytes):
            raise ValidationError("POP3 XOAUTH2 authentication failed.")
        return response

    @override
    def stls(self, context: ssl.SSLContext | None = None) -> bytes:
        previous_host = self.host
        self.host = self._tls_server_hostname
        try:
            return super().stls(context)
        finally:
            self.host = previous_host


class _OAuthPOP3SSL(poplib.POP3_SSL):
    _soai_ssl_context: ssl.SSLContext
    _tls_server_hostname: str
    sock: socket.socket

    def __init__(
        self,
        host: str,
        port: int = poplib.POP3_SSL_PORT,
        *,
        timeout: float = 60.0,
        context: ssl.SSLContext | None = None,
        tls_server_hostname: str,
    ) -> None:
        self._soai_ssl_context = context if context is not None else ssl.create_default_context()
        self._tls_server_hostname = tls_server_hostname
        super().__init__(host=host, port=port, timeout=timeout, context=context)

    def _create_socket(self, timeout: float | None) -> ssl.SSLSocket:
        sock = socket.create_connection((self.host, self.port), timeout)
        return self._soai_ssl_context.wrap_socket(sock, server_hostname=self._tls_server_hostname)

    def authenticate_xoauth2(self, sasl: str) -> bytes:
        auth_command = f"AUTH XOAUTH2 {sasl}\r\n".encode()
        self.sock.sendall(auth_command)
        response_reader = self.sock.makefile("rb")
        try:
            response = response_reader.readline()
        finally:
            response_reader.close()
        if not isinstance(response, bytes):
            raise ValidationError("POP3 XOAUTH2 authentication failed.")
        return response


def open_pop3_connection(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> POP3ConnectionProtocol:
    timeout = max(float(connect_timeout_sec), 1.0)
    ssl_context = ssl.create_default_context()
    if runtime_state.inbound_security == "tls":
        connection: POP3ConnectionProtocol = _OAuthPOP3SSL(
            host=connect_host,
            port=runtime_state.inbound_port,
            timeout=timeout,
            context=ssl_context,
            tls_server_hostname=runtime_state.inbound_host,
        )
    elif runtime_state.inbound_security == "starttls":
        connection = _OAuthPOP3(
            host=connect_host,
            port=runtime_state.inbound_port,
            timeout=timeout,
            tls_server_hostname=runtime_state.inbound_host,
        )
        connection.stls(context=ssl_context)
    else:
        raise ValidationError("inbound_security must be tls or starttls.")
    _authenticate_pop3_connection(connection=connection, auth_payload=auth_payload)
    return connection


def open_pop3_connection_context(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> AbstractContextManager[POP3ConnectionProtocol]:
    return closing(
        open_pop3_connection(
            runtime_state=runtime_state,
            auth_payload=auth_payload,
            connect_timeout_sec=connect_timeout_sec,
            connect_host=connect_host,
        ),
    )


@contextmanager
def open_pop3_uidl_listing_context(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> Generator[POP3UidlListing]:
    with open_pop3_connection_context(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        connect_host=connect_host,
    ) as connection:
        yield POP3UidlListing(connection=connection, entries=list_pop3_uidls(connection))


def list_pop3_uidls(connection: POP3ConnectionProtocol) -> list[tuple[int, str]]:
    response, lines, _octets = connection.uidl()
    if not isinstance(response, bytes) or not response.startswith(b"+OK"):
        raise ValidationError("POP3 UIDL failed.")
    entries: list[tuple[int, str]] = []
    for line in lines:
        if not isinstance(line, bytes):
            continue
        parts = line.decode("utf-8", errors="replace").split(" ", 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        entries.append((int(parts[0]), parts[1].strip()))
    return entries


def _authenticate_pop3_connection(
    *,
    connection: POP3ConnectionProtocol,
    auth_payload: JSONDict,
) -> None:
    auth_type, username, password, sasl = extract_mail_auth_payload_fields(auth_payload)
    if auth_type == "password":
        connection.user(username)
        connection.pass_(password)
        return
    if auth_type == "oauth2":
        if not sasl:
            raise ValidationError("POP3 XOAUTH2 SASL payload is required.")
        response = connection.authenticate_xoauth2(sasl)
        if not response.startswith(b"+OK"):
            raise ValidationError("POP3 XOAUTH2 authentication failed.")
        return
    raise ValidationError("POP3 auth_type is invalid.")
