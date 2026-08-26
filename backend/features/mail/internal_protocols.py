"""SoAI - Internal mail protocols [backend/features/mail/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ssl
from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.mail.protocols import MailRuntimeBindingsProtocol

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = (
    "MailCacheSyncServiceProtocol",
    "MailCalendarDateTimePropertyProtocol",
    "MailRemoteContentServiceProtocol",
    "MailRemoteSearchServiceProtocol",
    "MailRuntimeServiceProtocol",
    "POP3ConnectionProtocol",
)


class POP3ConnectionProtocol(Protocol):
    def stat(self) -> tuple[int, int]: ...
    def uidl(self) -> tuple[bytes, list[bytes], int]: ...
    def retr(self, which: int) -> tuple[bytes, list[bytes], int]: ...
    def dele(self, which: int) -> bytes: ...
    def quit(self) -> bytes: ...
    def close(self) -> None: ...
    def user(self, user: str) -> bytes: ...
    def pass_(self, password: str, /) -> bytes: ...
    def stls(self, context: ssl.SSLContext | None = None) -> bytes: ...
    def authenticate_xoauth2(self, sasl: str) -> bytes: ...


@runtime_checkable
class MailCalendarDateTimePropertyProtocol(Protocol):
    @property
    def dt(self) -> date | datetime: ...


class MailRuntimeServiceProtocol(MailRuntimeBindingsProtocol, Protocol):
    event_bus: EventBusProtocol


class MailCacheSyncServiceProtocol(MailRuntimeBindingsProtocol, Protocol): ...


class MailRemoteSearchServiceProtocol(MailRuntimeBindingsProtocol, Protocol): ...


class MailRemoteContentServiceProtocol(MailRuntimeBindingsProtocol, Protocol): ...
