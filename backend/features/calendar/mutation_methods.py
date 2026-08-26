"""SoAI - Calendar service mutation methods [backend/features/calendar/mutation_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from features.calendar.calendar_event_mutations import (
    respond_to_calendar_invite,
    update_calendar_event,
)
from features.calendar.calendar_event_support import require_id
from features.calendar.calendar_record_context import (
    load_calendar_row,
    load_event_row,
    require_calendar_account_id_from_row,
    require_event_calendar_id,
)
from features.calendar.calendar_sync import sync_calendar_account
from features.calendar.calendar_window_sync import sync_calendar_window
from features.calendar.internal_protocols import CalendarMutationServiceProtocol
from features.external_accounts.domain_account_actions import (
    coerce_action_status,
    format_account_action_result,
)

__all__ = (
    "respond_to_invite_method",
    "sync_account_method",
    "sync_window_method",
    "update_event_method",
)


async def sync_account_method(
    self: CalendarMutationServiceProtocol,
    *,
    user_id: int,
    account_id: str,
) -> JSONDict:
    async with self.account_lock(user_id=user_id, account_id=account_id):
        account = await self.database_calendar.get_account(user_id=user_id, account_id=account_id)
        if account is None:
            raise ValidationError("Calendar account not found.")
        details = await sync_calendar_account(self, user_id=user_id, account_id=account_id)
        return format_account_action_result(
            account_id=account_id,
            account_type="calendar",
            status=coerce_action_status(details.get("status"), default_value="ready"),
            details=details,
        )


async def sync_window_method(
    self: CalendarMutationServiceProtocol,
    *,
    user_id: int,
    calendar_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> JSONDict:
    calendar_row = await load_calendar_row(
        self.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    async with self.account_lock(
        user_id=user_id,
        account_id=require_calendar_account_id_from_row(calendar_row),
    ):
        return await sync_calendar_window(
            self,
            user_id=user_id,
            calendar_id=calendar_id,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        )


async def update_event_method(
    self: CalendarMutationServiceProtocol,
    *,
    user_id: int,
    payload: JSONDict,
) -> JSONDict:
    calendar_id = require_id(payload.get("calendar_id"), "calendar_id is required.")
    calendar_row = await load_calendar_row(
        self.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    async with self.account_lock(
        user_id=user_id,
        account_id=require_calendar_account_id_from_row(calendar_row),
    ):
        return await update_calendar_event(self, user_id=user_id, payload=payload)


async def respond_to_invite_method(
    self: CalendarMutationServiceProtocol,
    *,
    user_id: int,
    event_id: str,
    action: str,
    comment: str | None,
) -> JSONDict:
    event_row = await load_event_row(
        self.database_calendar,
        user_id=user_id,
        event_id=event_id,
    )
    calendar_row = await load_calendar_row(
        self.database_calendar,
        user_id=user_id,
        calendar_id=require_event_calendar_id(event_row),
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    async with self.account_lock(
        user_id=user_id,
        account_id=require_calendar_account_id_from_row(calendar_row),
    ):
        return await respond_to_calendar_invite(
            self,
            user_id=user_id,
            event_id=event_id,
            action=action,
            comment=comment,
        )
