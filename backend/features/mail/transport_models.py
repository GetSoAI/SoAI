"""SoAI - Mail transport dataclasses [backend/features/mail/transport_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "MailAccountRuntimeState",
    "MailFolderRuntimeState",
)


@dataclass(frozen=True, slots=True)
class MailAccountRuntimeState:
    account_id: str
    protocol: str
    inbound_host: str
    inbound_port: int
    inbound_security: str
    smtp_host: str
    smtp_port: int
    smtp_security: str
    folder_mapping: JSONDict | None
    account: JSONDict
    external_account: JSONDict


@dataclass(frozen=True, slots=True)
class MailFolderRuntimeState:
    folder_id: str
    remote_mailbox: str
    folder: JSONDict
