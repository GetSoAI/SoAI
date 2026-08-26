"""SoAI - Calendar CalDAV XML helpers [backend/features/calendar/calendar_xml.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from defusedxml.ElementTree import ParseError, fromstring

from core.errors.exceptions import ValidationError
from core.timing.formatting import timestamp_ms_to_utc_format
from core.types.json import JSONDict

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

__all__ = (
    "build_calendars_propfind_body",
    "build_discovery_propfind_body",
    "build_principal_propfind_body",
    "build_window_report_body",
    "parse_calendar_discovery",
    "parse_calendar_entries",
    "parse_calendar_report_entries",
)

_DAV_NS = "DAV:"
_CALDAV_NS = "urn:ietf:params:xml:ns:caldav"
_APPLE_ICAL_NS = "http://apple.com/ns/ical/"
_CALENDARSERVER_NS = "http://calendarserver.org/ns/"


def build_discovery_propfind_body() -> str:
    return (
        '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop>"
        "<d:current-user-principal/>"
        "<c:calendar-home-set/>"
        "<d:displayname/>"
        "<d:resourcetype/>"
        "</d:prop>"
        "</d:propfind>"
    )


def build_principal_propfind_body() -> str:
    return (
        '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop>"
        "<c:calendar-home-set/>"
        "<d:displayname/>"
        "</d:prop>"
        "</d:propfind>"
    )


def build_calendars_propfind_body() -> str:
    return (
        '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
        'xmlns:cs="http://calendarserver.org/ns/" xmlns:ical="http://apple.com/ns/ical/">'
        "<d:prop>"
        "<d:displayname/>"
        "<d:resourcetype/>"
        "<d:current-user-privilege-set/>"
        "<d:getetag/>"
        "<d:sync-token/>"
        "<ical:calendar-color/>"
        "<c:calendar-timezone/>"
        "<cs:getctag/>"
        "</d:prop>"
        "</d:propfind>"
    )


def build_window_report_body(*, window_start_ms: int, window_end_ms: int) -> str:
    start_token = _format_caldav_timestamp(window_start_ms)
    end_token = _format_caldav_timestamp(window_end_ms)
    return (
        '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop>"
        "<d:getetag/>"
        "<c:calendar-data/>"
        "</d:prop>"
        "<c:filter>"
        '<c:comp-filter name="VCALENDAR">'
        '<c:comp-filter name="VEVENT">'
        f'<c:time-range start="{start_token}" end="{end_token}"/>'
        "</c:comp-filter>"
        "</c:comp-filter>"
        "</c:filter>"
        "</c:calendar-query>"
    )


def parse_calendar_discovery(*, response_text: str, request_url: str) -> JSONDict:
    root = _parse_xml(response_text)
    principal_url: str | None = None
    calendar_home_url: str | None = None
    requested_resource_is_calendar = False
    for response in _iter_responses(root):
        href = _resolve_href(response, request_url)
        props = _read_ok_props(response)
        if _is_calendar_collection(props.get(_prop_name(_DAV_NS, "resourcetype"))):
            requested_resource_is_calendar = _matches_requested_url(href, request_url)
        principal_element = props.get(_prop_name(_DAV_NS, "current-user-principal"))
        if principal_url is None and principal_element is not None:
            principal_url = _extract_href(principal_element, request_url)
        home_element = props.get(_prop_name(_CALDAV_NS, "calendar-home-set"))
        if calendar_home_url is None and home_element is not None:
            calendar_home_url = _extract_href(home_element, request_url)
    return {
        "principal_url": principal_url,
        "calendar_home_url": calendar_home_url,
        "requested_resource_is_calendar": requested_resource_is_calendar,
    }


def parse_calendar_entries(*, response_text: str, request_url: str) -> list[JSONDict]:
    root = _parse_xml(response_text)
    calendars: list[JSONDict] = []
    seen_hrefs: set[str] = set()
    for response in _iter_responses(root):
        props = _read_ok_props(response)
        if not _is_calendar_collection(props.get(_prop_name(_DAV_NS, "resourcetype"))):
            continue
        href = _resolve_href(response, request_url)
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        display_name = _prop_text(props.get(_prop_name(_DAV_NS, "displayname")))
        color = _prop_text(props.get(_prop_name(_APPLE_ICAL_NS, "calendar-color")))
        sync_token = _prop_text(props.get(_prop_name(_DAV_NS, "sync-token")))
        read_only = not _has_write_privilege(
            props.get(_prop_name(_DAV_NS, "current-user-privilege-set")),
        )
        calendars.append(
            {
                "remote_href": href,
                "sync_token": sync_token,
                "etag": _prop_text(props.get(_prop_name(_DAV_NS, "getetag"))),
                "name": display_name or _default_calendar_name(href),
                "color": color,
                "timezone": None,
                "read_only": read_only,
            },
        )
    return calendars


def parse_calendar_report_entries(*, response_text: str, request_url: str) -> list[JSONDict]:
    root = _parse_xml(response_text)
    entries: list[JSONDict] = []
    for response in _iter_responses(root):
        href = _resolve_href(response, request_url)
        props = _read_ok_props(response)
        raw_ics = _prop_text(props.get(_prop_name(_CALDAV_NS, "calendar-data")))
        if raw_ics is None:
            continue
        entries.append(
            {
                "remote_href": href,
                "etag": _prop_text(props.get(_prop_name(_DAV_NS, "getetag"))),
                "raw_ics": raw_ics,
            },
        )
    return entries


def _parse_xml(value: str) -> Element:
    try:
        return fromstring(value)
    except ParseError as exception:
        raise ValidationError("CalDAV server returned invalid XML.") from exception


def _iter_responses(root: Element) -> list[Element]:
    return list(root.findall(f".//{{{_DAV_NS}}}response"))


def _read_ok_props(response: Element) -> dict[str, Element]:
    props: dict[str, Element] = {}
    for propstat in response.findall(f"./{{{_DAV_NS}}}propstat"):
        status = _prop_text(propstat.find(f"./{{{_DAV_NS}}}status"))
        if status is None or " 200 " not in f" {status} ":
            continue
        prop = propstat.find(f"./{{{_DAV_NS}}}prop")
        if prop is None:
            continue
        for child in list(prop):
            props[child.tag] = child
    return props


def _resolve_href(response: Element, request_url: str) -> str:
    href_text = _prop_text(response.find(f"./{{{_DAV_NS}}}href"))
    if href_text is None:
        return request_url
    return urljoin(request_url, href_text)


def _extract_href(element: Element, request_url: str) -> str | None:
    href_text = _prop_text(element.find(f".//{{{_DAV_NS}}}href"))
    if href_text is None:
        return None
    return urljoin(request_url, href_text)


def _is_calendar_collection(element: Element | None) -> bool:
    if element is None:
        return False
    tags = {child.tag for child in list(element)}
    return _prop_name(_CALDAV_NS, "calendar") in tags


def _has_write_privilege(element: Element | None) -> bool:
    if element is None:
        return True
    for privilege in element.findall(f".//{{{_DAV_NS}}}privilege"):
        tags = {child.tag for child in list(privilege)}
        if _prop_name(_DAV_NS, "write") in tags or _prop_name(_DAV_NS, "all") in tags:
            return True
    return False


def _default_calendar_name(href: str) -> str:
    path = urlsplit(href).path.rstrip("/")
    if not path:
        return "Calendar"
    return path.rsplit("/", 1)[-1] or "Calendar"


def _matches_requested_url(href: str, request_url: str) -> bool:
    return href.rstrip("/") == request_url.rstrip("/")


def _prop_name(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _prop_text(element: Element | None) -> str | None:
    if element is None:
        return None
    text_value = "".join(element.itertext()).strip()
    return text_value or None


def _format_caldav_timestamp(timestamp_ms: int) -> str:
    return timestamp_ms_to_utc_format(timestamp_ms, "%Y%m%dT%H%M%SZ")
