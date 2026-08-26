"""SoAI - Calendar service transport preparation [backend/features/calendar/calendar_transport_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.calendar.calendar_caldav_context import (
    PreparedCalendarTransportContext,
    prepare_calendar_transport_context,
)
from features.calendar.internal_protocols import (
    CalendarAccountTestingServiceProtocol,
    CalendarMutationServiceProtocol,
    CalendarSyncServiceProtocol,
)

__all__ = ("prepare_service_calendar_transport_context",)


async def prepare_service_calendar_transport_context(
    service: (
        CalendarAccountTestingServiceProtocol
        | CalendarMutationServiceProtocol
        | CalendarSyncServiceProtocol
    ),
    *,
    user_id: int,
    account_id: str,
) -> PreparedCalendarTransportContext:
    async with service.account_lock(user_id=user_id, account_id=account_id):
        return await prepare_calendar_transport_context(
            config=service.config,
            runtime_flags=service.runtime_flags,
            database_calendar=service.database_calendar,
            external_accounts=service.external_accounts,
            user_id=user_id,
            account_id=account_id,
            validate_endpoint=True,
        )
