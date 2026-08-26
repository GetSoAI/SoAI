"""SoAI - Calendar service formatting helpers [backend/features/calendar/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.external_accounts.state import is_external_account_ready
from core.types.json import JSONDict, JSONValue
from features.external_accounts.account_actions import (
    resolve_domain_account_supported_actions,
)
from features.external_accounts.account_envelope import (
    build_account_envelope,
    resolve_external_account_oauth_status,
)
from features.external_accounts.external_account_fields import (
    require_external_account_auth_type,
)

__all__ = (
    "format_calendar_account",
    "format_calendar_entry",
    "format_calendar_event",
)


def format_calendar_account(
    calendar_account: JSONDict,
    external_account: JSONDict,
) -> JSONDict:
    auth_type = require_external_account_auth_type(
        external_account,
        build_error=StateError,
    )
    account_id_value = calendar_account.get("id")
    if not isinstance(account_id_value, str) or not account_id_value.strip():
        raise StateError("Calendar account id is invalid.")
    return build_account_envelope(
        account_id=account_id_value,
        account_type="calendar",
        default_label=account_id_value,
        external_account=external_account,
        supported_actions=_calendar_account_supported_actions(
            auth_type=auth_type,
            has_password=external_account.get("has_password") is True,
            oauth_status=resolve_external_account_oauth_status(external_account),
        ),
        capabilities={
            "supports_sync": True,
            "supports_oauth": auth_type == "oauth2",
            "supports_linked_mail_account": True,
        },
        transport={
            "caldav_base_url": calendar_account.get("caldav_base_url"),
            "discovered_principal": calendar_account.get("discovered_principal"),
            "linked_mail_account_id": calendar_account.get("linked_mail_account_id"),
        },
        raw_sync_at_ms=calendar_account.get("last_sync_at_ms"),
        raw_sync_error=calendar_account.get("last_sync_error"),
    )


def format_calendar_entry(calendar_row: JSONDict) -> JSONDict:
    result = dict(calendar_row)
    result["calendar_id"] = calendar_row.get("id")
    result["supported_actions"] = (
        []
        if calendar_row.get("read_only") is True
        else [
            "sync_window",
            "create",
            "update",
            "delete",
        ]
    )
    result.pop("id", None)
    return result


def format_calendar_event(event_row: JSONDict) -> JSONDict:
    result = dict(event_row)
    result["event_id"] = event_row.get("id")
    supported_actions = ["update", "delete"]
    if _calendar_event_is_respondable(event_row):
        supported_actions.append("respond")
    result["supported_actions"] = supported_actions
    result.pop("id", None)
    return result


def _calendar_account_supported_actions(
    *,
    auth_type: str,
    has_password: bool,
    oauth_status: JSONValue,
) -> list[str]:
    normalized_oauth_status = oauth_status if isinstance(oauth_status, str) else ""
    return resolve_domain_account_supported_actions(
        auth_type=auth_type,
        ready=is_external_account_ready(
            auth_type=auth_type,
            has_password=has_password,
            oauth_status=normalized_oauth_status,
        ),
        ready_actions=("test", "sync"),
    )


def _calendar_event_is_respondable(event_row: JSONDict) -> bool:
    organizer_value = event_row.get("organizer")
    if not isinstance(organizer_value, dict):
        return False
    attendee_count = event_row.get("attendee_count")
    return isinstance(attendee_count, int) and attendee_count > 0
