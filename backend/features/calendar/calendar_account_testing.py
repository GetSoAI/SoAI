"""SoAI - Calendar account connectivity testing [backend/features/calendar/calendar_account_testing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from features.calendar.calendar_caldav_client import discover_calendar_account
from features.calendar.calendar_transport_preparation import (
    prepare_service_calendar_transport_context,
)
from features.calendar.internal_protocols import CalendarAccountTestingServiceProtocol

__all__ = ("test_calendar_account",)


async def test_calendar_account(
    service: CalendarAccountTestingServiceProtocol,
    *,
    user_id: int,
    account_id: str,
) -> JSONDict:
    prepared = await prepare_service_calendar_transport_context(
        service,
        user_id=user_id,
        account_id=account_id,
    )
    discovery = await discover_calendar_account(
        http_client=service.http_client,
        prepared=prepared,
    )
    calendars_value = discovery.get("calendars")
    calendars = calendars_value if isinstance(calendars_value, list) else []
    return {
        "ok": True,
        "account_id": account_id,
        "status": "ready",
        "principal_url": discovery.get("principal_url"),
        "calendar_home_url": discovery.get("calendar_home_url"),
        "calendars_count": len(calendars),
    }
