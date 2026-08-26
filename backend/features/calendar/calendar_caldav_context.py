"""SoAI - Calendar CalDAV context helpers [backend/features/calendar/calendar_caldav_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.network.urls import require_absolute_http_url
from core.runtime.network_policy import validate_runtime_url
from core.serialization.base64_values import encode_base64_ascii
from core.types.json import JSONDict
from core.validation.strings import (
    coerce_optional_trimmed_str,
    coerce_trimmed_str_or_empty,
)
from features.external_accounts.authentication import (
    resolve_external_account_authentication,
)
from features.external_accounts.linked_external_account_loading import (
    load_linked_external_account,
)

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from features.external_accounts.authentication import ExternalAccountAuthentication

__all__ = (
    "CalendarAccountRuntimeState",
    "PreparedCalendarTransportContext",
    "load_calendar_account_runtime",
    "prepare_calendar_transport_context",
    "validate_calendar_endpoint",
)


@dataclass(frozen=True, slots=True)
class CalendarAccountRuntimeState:
    account_id: str
    caldav_base_url: str
    linked_mail_account_id: str | None
    discovered_principal: JSONDict | None
    account: JSONDict
    external_account: JSONDict


@dataclass(frozen=True, slots=True)
class PreparedCalendarTransportContext:
    runtime_state: CalendarAccountRuntimeState
    account_username: str
    request_headers: dict[str, str]
    request_timeout_sec: float


async def prepare_calendar_transport_context(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    database_calendar: DatabaseCalendarProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account_id: str,
    validate_endpoint: bool,
) -> PreparedCalendarTransportContext:
    runtime_state = await load_calendar_account_runtime(
        database_calendar=database_calendar,
        external_accounts=external_accounts,
        user_id=user_id,
        account_id=account_id,
        decrypt_secrets=True,
    )
    if validate_endpoint:
        await validate_calendar_endpoint(
            runtime_flags,
            base_url=runtime_state.caldav_base_url,
        )
    resolved_authentication = await resolve_external_account_authentication(
        external_accounts=external_accounts,
        external_account=runtime_state.external_account,
        user_id=user_id,
        missing_access_token_message="OAuth access token is required.",
        build_xoauth2_sasl=False,
    )
    request_headers = _build_calendar_auth_headers(
        resolved_authentication=resolved_authentication,
    )
    request_timeout_sec = float(config.get_float("INTEGRATIONS.CALENDAR.TIMEOUTS.REQUEST_SEC"))
    return PreparedCalendarTransportContext(
        runtime_state=runtime_state,
        account_username=resolved_authentication.username,
        request_headers=request_headers,
        request_timeout_sec=request_timeout_sec,
    )


async def load_calendar_account_runtime(
    *,
    database_calendar: DatabaseCalendarProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account_id: str,
    decrypt_secrets: bool,
) -> CalendarAccountRuntimeState:
    linked_account = await load_linked_external_account(
        account_reader=database_calendar,
        external_accounts=external_accounts,
        user_id=user_id,
        account_id=account_id,
        decrypt_secrets=decrypt_secrets,
        missing_account_message="Calendar account not found.",
        missing_external_account_id_message="Calendar account is missing its external account id.",
        changed_external_account_id_message=(
            "Calendar account external account id changed during runtime load."
        ),
        missing_external_account_message="Calendar external account not found.",
    )
    locked_account = linked_account.locked_account
    caldav_base_url = coerce_trimmed_str_or_empty(locked_account.get("caldav_base_url"))
    if not caldav_base_url:
        raise StateError("Calendar account caldav_base_url is invalid.")
    linked_mail_account_id = coerce_optional_trimmed_str(
        locked_account.get("linked_mail_account_id"),
    )
    discovered_principal_value = locked_account.get("discovered_principal")
    discovered_principal = (
        discovered_principal_value if isinstance(discovered_principal_value, dict) else None
    )
    return CalendarAccountRuntimeState(
        account_id=account_id,
        caldav_base_url=caldav_base_url,
        linked_mail_account_id=linked_mail_account_id,
        discovered_principal=discovered_principal,
        account=locked_account,
        external_account=linked_account.external_account,
    )


async def validate_calendar_endpoint(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    base_url: str,
) -> None:
    try:
        normalized_base_url = require_absolute_http_url(base_url)
    except ValidationError as exception:
        raise ValidationError("caldav_base_url is invalid.") from exception
    await validate_runtime_url(
        runtime_flags,
        normalized_base_url,
        source="calendar caldav endpoint",
    )


def _build_calendar_auth_headers(
    *,
    resolved_authentication: ExternalAccountAuthentication,
) -> dict[str, str]:
    if resolved_authentication.auth_type == "password":
        password = resolved_authentication.password
        if password is None:
            raise ValidationError("External account password is required.")
        basic_token = encode_base64_ascii(
            f"{resolved_authentication.username}:{password}".encode(),
        )
        return {"Authorization": f"Basic {basic_token}"}
    bearer_token = resolved_authentication.access_token
    if not bearer_token:
        raise ValidationError("OAuth access token is required.")
    return {"Authorization": f"Bearer {bearer_token}"}
