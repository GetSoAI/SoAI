"""SoAI - Mail transport preparation helpers [backend/features/mail/transport_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from features.mail.authentication import resolve_mail_authentication
from features.mail.endpoint_policy import validate_mail_endpoints
from features.mail.runtime_state import load_mail_account_runtime

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.mail.protocols import DatabaseMailProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "PreparedMailTransportContext",
    "prepare_mail_transport_context",
)


@dataclass(frozen=True, slots=True)
class PreparedMailTransportContext:
    runtime_state: MailAccountRuntimeState
    auth_payload: JSONDict
    connect_timeout_sec: float
    inbound_connect_host: str
    smtp_connect_host: str


async def prepare_mail_transport_context(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    database_mail: DatabaseMailProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account_id: str,
) -> PreparedMailTransportContext:
    runtime_state = await load_mail_account_runtime(
        database_mail=database_mail,
        external_accounts=external_accounts,
        user_id=user_id,
        account_id=account_id,
        decrypt_secrets=True,
    )
    endpoint_targets = await validate_mail_endpoints(
        runtime_flags,
        inbound_host=runtime_state.inbound_host,
        inbound_port=runtime_state.inbound_port,
        smtp_host=runtime_state.smtp_host,
        smtp_port=runtime_state.smtp_port,
    )
    auth_payload = await resolve_mail_authentication(
        runtime_state=runtime_state,
        external_accounts=external_accounts,
        user_id=user_id,
    )
    connect_timeout_sec = float(config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.CONNECT_SEC"))
    return PreparedMailTransportContext(
        runtime_state=runtime_state,
        auth_payload=auth_payload,
        connect_timeout_sec=connect_timeout_sec,
        inbound_connect_host=endpoint_targets.inbound_connect_host,
        smtp_connect_host=endpoint_targets.smtp_connect_host,
    )
