"""SoAI - Mail service formatting helpers [backend/features/mail/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from features.external_accounts.account_envelope import build_account_envelope
from features.external_accounts.external_account_fields import (
    require_external_account_auth_type,
)
from features.mail.account_readiness import resolve_mail_account_supported_actions
from features.mail.mail_account_context import require_mail_account_protocol

__all__ = (
    "format_mail_account",
    "format_mail_folder",
    "format_mail_message",
)


def format_mail_account(mail_account: JSONDict, external_account: JSONDict) -> JSONDict:
    protocol = require_mail_account_protocol(mail_account)
    auth_type = require_external_account_auth_type(
        external_account,
        build_error=StateError,
    )
    account_id_value = mail_account.get("id")
    if not isinstance(account_id_value, str) or not account_id_value.strip():
        raise StateError("Mail account id is invalid.")
    return build_account_envelope(
        account_id=account_id_value,
        account_type="mail",
        default_label=account_id_value,
        external_account=external_account,
        supported_actions=resolve_mail_account_supported_actions(
            mail_account,
            external_account,
        ),
        capabilities={
            "supports_sync": True,
            "supports_oauth": auth_type == "oauth2",
            "supports_drafts": protocol == "imap",
            "supports_folder_mutation": protocol == "imap",
        },
        transport={
            "protocol": protocol,
            "inbound": {
                "host": mail_account.get("inbound_host"),
                "port": mail_account.get("inbound_port"),
                "security": mail_account.get("inbound_security"),
            },
            "outbound": {
                "host": mail_account.get("smtp_host"),
                "port": mail_account.get("smtp_port"),
                "security": mail_account.get("smtp_security"),
            },
            "folder_mapping": mail_account.get("folder_mapping"),
        },
        raw_sync_at_ms=mail_account.get("last_sync_at_ms"),
        raw_sync_error=mail_account.get("last_sync_error"),
    )


def format_mail_folder(folder: JSONDict, *, protocol: str) -> JSONDict:
    result = dict(folder)
    result["folder_id"] = folder.get("id")
    result["supported_actions"] = _folder_supported_actions(protocol)
    result.pop("id", None)
    return result


def format_mail_message(message: JSONDict, *, protocol: str) -> JSONDict:
    result = dict(message)
    result["message_id"] = message.get("id")
    result["supported_actions"] = _message_supported_actions(protocol)
    result.pop("id", None)
    return result


def _folder_supported_actions(protocol: str) -> list[str]:
    if protocol != "imap":
        return []
    return ["create", "rename", "delete", "subscribe", "unsubscribe"]


def _message_supported_actions(protocol: str) -> list[str]:
    actions = ["mark_read", "mark_unread", "delete"]
    if protocol == "imap":
        actions.extend(["flag", "unflag", "archive", "unarchive", "move", "copy", "restore"])
    return actions
