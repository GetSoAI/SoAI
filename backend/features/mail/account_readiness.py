"""SoAI - Mail account readiness rules [backend/features/mail/account_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError, ValidationError
from core.external_accounts.state import is_external_account_ready
from core.types.json import JSONDict
from features.external_accounts.account_actions import (
    resolve_domain_account_supported_actions,
)
from features.external_accounts.account_envelope import (
    resolve_external_account_oauth_status,
)
from features.external_accounts.external_account_fields import (
    require_external_account_auth_type,
)
from features.mail.mail_account_context import require_mail_account_protocol

__all__ = (
    "require_mail_account_compose_ready",
    "resolve_mail_account_supported_actions",
)


def resolve_mail_account_supported_actions(
    mail_account: JSONDict,
    external_account: JSONDict,
) -> list[str]:
    protocol = require_mail_account_protocol(mail_account)
    auth_type = require_external_account_auth_type(
        external_account,
        build_error=StateError,
    )
    ready = protocol in {"imap", "pop3"} and is_external_account_ready(
        auth_type=auth_type,
        has_password=external_account.get("has_password") is True,
        oauth_status=resolve_external_account_oauth_status(external_account),
    )
    return resolve_domain_account_supported_actions(
        auth_type=auth_type,
        ready=ready,
        ready_actions=("test", "sync", "compose"),
    )


def require_mail_account_compose_ready(
    mail_account: JSONDict,
    external_account: JSONDict,
) -> None:
    if "compose" in resolve_mail_account_supported_actions(mail_account, external_account):
        return
    raise ValidationError("Linked mail account is not ready for compose operations.")
