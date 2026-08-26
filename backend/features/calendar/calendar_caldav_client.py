"""SoAI - Calendar CalDAV client helpers [backend/features/calendar/calendar_caldav_client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx2

from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.types.json import JSONDict
from features.calendar.calendar_xml import (
    build_calendars_propfind_body,
    build_discovery_propfind_body,
    build_principal_propfind_body,
    build_window_report_body,
    parse_calendar_discovery,
    parse_calendar_entries,
    parse_calendar_report_entries,
)

if TYPE_CHECKING:
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )

__all__ = (
    "delete_remote_calendar_event",
    "discover_calendar_account",
    "put_remote_calendar_event",
    "read_calendar_window_events",
    "read_remote_calendar_event",
)


async def discover_calendar_account(
    *,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
) -> JSONDict:
    base_url = prepared.runtime_state.caldav_base_url
    discovery_response = await _request_caldav(
        http_client=http_client,
        method="PROPFIND",
        url=base_url,
        headers={"Depth": "0"},
        request_headers=prepared.request_headers,
        content=build_discovery_propfind_body(),
        timeout_sec=prepared.request_timeout_sec,
        expected_statuses=(207,),
    )
    discovery = parse_calendar_discovery(
        response_text=discovery_response.text,
        request_url=base_url,
    )
    principal_url = str(discovery.get("principal_url") or "")
    calendar_home_url = str(discovery.get("calendar_home_url") or "")
    if principal_url and not calendar_home_url:
        principal_response = await _request_caldav(
            http_client=http_client,
            method="PROPFIND",
            url=principal_url,
            headers={"Depth": "0"},
            request_headers=prepared.request_headers,
            content=build_principal_propfind_body(),
            timeout_sec=prepared.request_timeout_sec,
            expected_statuses=(207,),
        )
        principal_discovery = parse_calendar_discovery(
            response_text=principal_response.text,
            request_url=principal_url,
        )
        calendar_home_url = str(principal_discovery.get("calendar_home_url") or "")
    target_url = calendar_home_url or base_url
    calendars_response = await _request_caldav(
        http_client=http_client,
        method="PROPFIND",
        url=target_url,
        headers={"Depth": "1"},
        request_headers=prepared.request_headers,
        content=build_calendars_propfind_body(),
        timeout_sec=prepared.request_timeout_sec,
        expected_statuses=(207,),
    )
    calendars = parse_calendar_entries(
        response_text=calendars_response.text,
        request_url=target_url,
    )
    if not calendars and discovery.get("requested_resource_is_calendar") is True:
        calendars = [
            {
                "remote_href": base_url,
                "sync_token": None,
                "etag": None,
                "name": "Calendar",
                "color": None,
                "timezone": None,
                "read_only": False,
            },
        ]
    return {
        "principal_url": principal_url or None,
        "calendar_home_url": target_url,
        "calendars": calendars,
    }


async def read_calendar_window_events(
    *,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
    calendar_href: str,
    window_start_ms: int,
    window_end_ms: int,
) -> list[JSONDict]:
    response = await _request_caldav(
        http_client=http_client,
        method="REPORT",
        url=calendar_href,
        headers={"Depth": "1"},
        request_headers=prepared.request_headers,
        content=build_window_report_body(
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        ),
        timeout_sec=prepared.request_timeout_sec,
        expected_statuses=(207,),
    )
    return parse_calendar_report_entries(
        response_text=response.text,
        request_url=calendar_href,
    )


async def read_remote_calendar_event(
    *,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
    event_href: str,
) -> JSONDict:
    response = await _request_caldav(
        http_client=http_client,
        method="GET",
        url=event_href,
        headers={"Accept": "text/calendar"},
        request_headers=prepared.request_headers,
        content=None,
        timeout_sec=prepared.request_timeout_sec,
        expected_statuses=(200,),
    )
    return {
        "remote_href": event_href,
        "etag": response.headers.get("ETag"),
        "raw_ics": response.text,
    }


async def put_remote_calendar_event(
    *,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
    calendar_href: str,
    event_href: str | None,
    uid: str,
    raw_ics: str,
    etag: str | None,
) -> JSONDict:
    target_url = event_href or _build_event_href(calendar_href=calendar_href, uid=uid)
    headers: dict[str, str] = {"Content-Type": "text/calendar; charset=utf-8"}
    if etag is None:
        headers["If-None-Match"] = "*"
    else:
        headers["If-Match"] = etag
    response = await _request_caldav(
        http_client=http_client,
        method="PUT",
        url=target_url,
        headers=headers,
        request_headers=prepared.request_headers,
        content=raw_ics,
        timeout_sec=prepared.request_timeout_sec,
        expected_statuses=(200, 201, 204),
    )
    response_etag = response.headers.get("ETag")
    return {"remote_href": target_url, "etag": response_etag}


async def delete_remote_calendar_event(
    *,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
    event_href: str,
    etag: str | None,
) -> None:
    headers: dict[str, str] = {}
    if etag is not None:
        headers["If-Match"] = etag
    await _request_caldav(
        http_client=http_client,
        method="DELETE",
        url=event_href,
        headers=headers,
        request_headers=prepared.request_headers,
        content=None,
        timeout_sec=prepared.request_timeout_sec,
        expected_statuses=(200, 204),
    )


async def _request_caldav(
    *,
    http_client: httpx2.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    request_headers: dict[str, str],
    content: str | None,
    timeout_sec: float,
    expected_statuses: tuple[int, ...],
) -> httpx2.Response:
    merged_headers = dict(request_headers)
    merged_headers.update(headers)
    try:
        response = await http_client.request(
            method,
            url,
            headers=merged_headers,
            content=content.encode("utf-8") if isinstance(content, str) else None,
            timeout=timeout_sec,
        )
    except httpx2.TimeoutException as exception:
        raise SoAITimeoutError(
            f"CalDAV request timed out after {timeout_sec}s: {url}",
            details={"url": url, "timeout_sec": float(timeout_sec)},
            cause=exception,
        ) from exception
    except httpx2.RequestError as exception:
        raise ExternalServiceError(
            f"Could not connect to CalDAV server at {url}.",
            details={"url": url},
            cause=exception,
        ) from exception
    if response.status_code not in expected_statuses:
        raise ValidationError(_build_caldav_error_message(response))
    return response


def _build_event_href(*, calendar_href: str, uid: str) -> str:
    normalized_calendar_href = f"{calendar_href.rstrip('/')}/"
    return urljoin(normalized_calendar_href, f"{uid}.ics")


def _build_caldav_error_message(response: httpx2.Response) -> str:
    status_code = response.status_code
    reason = response.reason_phrase.strip() if response.reason_phrase else "request failed"
    message = f"CalDAV request failed with HTTP {status_code} {reason}."
    if status_code == 401:
        raise ValidationError("Calendar authentication failed.")
    if status_code == 403:
        raise ValidationError("Calendar access was denied by the CalDAV server.")
    if status_code == 404:
        raise ValidationError("CalDAV resource was not found.")
    if status_code == 412:
        raise ValidationError("Calendar event precondition failed due to an ETag mismatch.")
    if status_code == 409:
        raise ValidationError("Calendar event could not be stored due to a remote conflict.")
    if status_code >= 500:
        raise ExternalServiceError(message, details={"status_code": int(status_code)})
    return message
