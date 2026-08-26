"""SoAI - Mail IMAP session management [backend/features/mail/imap_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import imaplib
import logging
import socket
import ssl
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal, override

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.logging.trace import get_logger
from features.mail.auth_payload_fields import extract_mail_auth_payload_fields

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = ("open_imap_connection",)

OPERATION = "features.mail.imap_session.open_imap_connection"
LOGGER_NAME = "SoAI.features.mail.imap_session"
IMAP_PORT = 143
IMAP_SSL_PORT = 993


class _SoAIIMAP4(imaplib.IMAP4):
    __slots__ = ("_tls_server_hostname",)

    def __init__(
        self,
        host: str = "",
        port: int = IMAP_PORT,
        timeout: float | None = None,
        *,
        tls_server_hostname: str,
    ) -> None:
        self._tls_server_hostname = tls_server_hostname
        self.host = host
        super().__init__(host=host, port=port, timeout=timeout)

    @override
    def starttls(
        self,
        ssl_context: ssl.SSLContext | None = None,
    ) -> tuple[Literal["OK"], list[None]]:
        previous_host = self._get_host()
        self._set_host(self._tls_server_hostname)
        try:
            return super().starttls(ssl_context)
        finally:
            self._set_host(previous_host)

    def _get_host(self) -> str:
        return self.host

    def _set_host(self, value: str) -> None:
        self.host = value

    if TYPE_CHECKING:

        @override
        def close(self) -> tuple[str, list[bytes]]: ...


class _SoAIIMAP4SSL(imaplib.IMAP4_SSL):
    __slots__ = ("_soai_ssl_context", "_tls_server_hostname")

    def __init__(
        self,
        host: str = "",
        port: int = IMAP_SSL_PORT,
        *,
        timeout: float | None = None,
        ssl_context: ssl.SSLContext | None = None,
        tls_server_hostname: str,
    ) -> None:
        self._soai_ssl_context = (
            ssl_context if ssl_context is not None else ssl.create_default_context()
        )
        self._tls_server_hostname = tls_server_hostname
        super().__init__(host=host, port=port, timeout=timeout, ssl_context=ssl_context)

    def _create_socket(self, timeout: float | None) -> ssl.SSLSocket:
        sock = socket.create_connection((self.host, self.port), timeout)
        return self._soai_ssl_context.wrap_socket(sock, server_hostname=self._tls_server_hostname)

    if TYPE_CHECKING:

        @override
        def close(self) -> tuple[str, list[bytes]]: ...


if TYPE_CHECKING:
    type IMAPConnection = _SoAIIMAP4 | _SoAIIMAP4SSL
else:

    class IMAPConnection:
        __slots__ = ()


@contextmanager
def open_imap_connection(
    *,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
) -> Generator[IMAPConnection]:
    timeout = max(float(connect_timeout_sec), 1.0)
    ssl_context = ssl.create_default_context()
    connection: IMAPConnection | None = None
    if runtime_state.inbound_security == "tls":
        try:
            connection = _SoAIIMAP4SSL(
                host=connect_host,
                port=runtime_state.inbound_port,
                timeout=timeout,
                ssl_context=ssl_context,
                tls_server_hostname=runtime_state.inbound_host,
            )
        except TimeoutError as exception:
            raise SoAITimeoutError(
                _build_imap_connect_timeout_message(runtime_state, timeout=timeout),
                details=_build_imap_endpoint_details(runtime_state),
                operation=OPERATION,
                cause=exception,
            ) from exception
        except (OSError, ssl.SSLError, imaplib.IMAP4.error) as exception:
            raise ExternalServiceError(
                _build_imap_connect_failed_message(runtime_state),
                details=_build_imap_endpoint_details(runtime_state),
                operation=OPERATION,
                cause=exception,
            ) from exception
    elif runtime_state.inbound_security == "starttls":
        try:
            connection = _SoAIIMAP4(
                host=connect_host,
                port=runtime_state.inbound_port,
                timeout=timeout,
                tls_server_hostname=runtime_state.inbound_host,
            )
            connection.starttls(ssl_context)
        except TimeoutError as exception:
            raise SoAITimeoutError(
                _build_imap_connect_timeout_message(runtime_state, timeout=timeout),
                details=_build_imap_endpoint_details(runtime_state),
                operation=OPERATION,
                cause=exception,
            ) from exception
        except imaplib.IMAP4.error as exception:
            raise ValidationError("IMAP STARTTLS failed.") from exception
        except (OSError, ssl.SSLError) as exception:
            raise ExternalServiceError(
                _build_imap_connect_failed_message(runtime_state),
                details=_build_imap_endpoint_details(runtime_state),
                operation=OPERATION,
                cause=exception,
            ) from exception
    else:
        raise ValidationError("inbound_security must be tls or starttls.")
    try:
        if connection is None:
            raise ValidationError("IMAP connection is unavailable.")
        _authenticate(connection=connection, auth_payload=auth_payload)
    except (ValidationError, OSError, imaplib.IMAP4.error):
        if connection is not None:
            _logout_after_authentication_error_safely(
                connection,
                details=_build_imap_endpoint_details(runtime_state),
            )
        raise
    try:
        if connection is None:
            raise ValidationError("IMAP connection is unavailable.")
        yield connection
    finally:
        if connection is not None:
            _logout_after_session_safely(
                connection,
                details=_build_imap_endpoint_details(runtime_state),
            )


def _authenticate(*, connection: IMAPConnection, auth_payload: JSONDict) -> None:
    auth_type, username, password, sasl = extract_mail_auth_payload_fields(auth_payload)
    if auth_type == "password":
        try:
            connection.login(username, password)
        except imaplib.IMAP4.error as exception:
            raise ValidationError("IMAP authentication failed.") from exception
        return
    if auth_type == "oauth2":
        try:
            connection.authenticate("XOAUTH2", lambda _challenge: sasl.encode("ascii"))
        except imaplib.IMAP4.error as exception:
            raise ValidationError("IMAP authentication failed.") from exception
        return
    raise ValidationError("IMAP auth_type is invalid.")


def _build_imap_connect_failed_message(runtime_state: MailAccountRuntimeState) -> str:
    security = runtime_state.inbound_security.strip() if runtime_state.inbound_security else ""
    host = runtime_state.inbound_host.strip() if runtime_state.inbound_host else ""
    port = int(runtime_state.inbound_port)
    normalized_security = security or "unknown"
    normalized_host = host or "unknown-host"
    return (
        f"Could not connect to IMAP server at {normalized_host}:{port} "
        f"(security={normalized_security})."
    )


def _build_imap_connect_timeout_message(
    runtime_state: MailAccountRuntimeState,
    *,
    timeout: float,
) -> str:
    security = runtime_state.inbound_security.strip() if runtime_state.inbound_security else ""
    host = runtime_state.inbound_host.strip() if runtime_state.inbound_host else ""
    port = int(runtime_state.inbound_port)
    normalized_security = security or "unknown"
    normalized_host = host or "unknown-host"
    timeout_label = float(timeout)
    return (
        f"IMAP connection timed out after {timeout_label}s while connecting to "
        f"{normalized_host}:{port} (security={normalized_security})."
    )


def _build_imap_endpoint_details(runtime_state: MailAccountRuntimeState) -> dict[str, str | int]:
    host = runtime_state.inbound_host.strip() if runtime_state.inbound_host else ""
    port = int(runtime_state.inbound_port)
    security = runtime_state.inbound_security.strip() if runtime_state.inbound_security else ""
    return {"host": host, "port": port, "security": security}


def _logout_after_authentication_error_safely(
    connection: IMAPConnection,
    *,
    details: dict[str, str | int],
) -> None:
    try:
        connection.logout()
    except (OSError, imaplib.IMAP4.error) as exception:
        log_exception(
            _imap_session_logger(),
            exception,
            message="IMAP logout failed after authentication error (non-critical).",
            operation=OPERATION,
            level="debug",
            details=details,
        )


def _logout_after_session_safely(
    connection: IMAPConnection,
    *,
    details: dict[str, str | int],
) -> None:
    try:
        connection.logout()
    except (OSError, imaplib.IMAP4.error) as exception:
        log_exception(
            _imap_session_logger(),
            exception,
            message="IMAP logout failed (non-critical).",
            operation=OPERATION,
            level="debug",
            details=details,
        )


def _imap_session_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
