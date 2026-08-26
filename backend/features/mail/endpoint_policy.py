"""SoAI - Mail endpoint policy enforcement [backend/features/mail/endpoint_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.runtime.network_policy import validate_runtime_host_port

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "MailEndpointTargets",
    "validate_mail_endpoint",
    "validate_mail_endpoints",
)


@dataclass(frozen=True, slots=True)
class MailEndpointTargets:
    inbound_connect_host: str
    smtp_connect_host: str


async def validate_mail_endpoint(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    host: str,
    port: int,
    source: str,
) -> str:
    pinned_host = await validate_runtime_host_port(
        runtime_flags,
        host=host,
        port=port,
        source=source,
    )
    return pinned_host or host


async def validate_mail_endpoints(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    inbound_host: str,
    inbound_port: int,
    smtp_host: str,
    smtp_port: int,
) -> MailEndpointTargets:
    inbound_connect_host = await validate_mail_endpoint(
        runtime_flags,
        host=inbound_host,
        port=inbound_port,
        source="mail inbound endpoint",
    )
    smtp_connect_host = await validate_mail_endpoint(
        runtime_flags,
        host=smtp_host,
        port=smtp_port,
        source="mail smtp endpoint",
    )
    return MailEndpointTargets(
        inbound_connect_host=inbound_connect_host,
        smtp_connect_host=smtp_connect_host,
    )
