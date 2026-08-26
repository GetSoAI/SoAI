"""SoAI - WebUI-only tool icon catalog [backend/features/api/routes/webui/tool_icon_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import base64
from collections.abc import Mapping
from urllib.parse import unquote

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from fastapi import Depends

from core.errors.exceptions import ValidationError
from core.mcp.qualified_name import encode_qualified_tool_name
from core.network.percent_encoding import is_valid_percent_encoding
from core.types.json import JSONDict, JSONValue
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.webui_tool_icons import (
    WebuiToolIcon,
    WebuiToolIconCatalogResponse,
)

__all__ = ("register_routes",)

MAX_TOOL_ICON_SOURCE_BYTES = 8_192
SVG_DATA_URI_PREFIX = "data:image/svg+xml"
SVG_XML_TAG = "{http://www.w3.org/2000/svg}svg"
ALLOWED_SVG_TAGS = frozenset(
    (
        "svg",
        "g",
        "path",
        "circle",
        "rect",
        "line",
        "polyline",
        "polygon",
        "ellipse",
        "title",
        "desc",
    ),
)
ALLOWED_SVG_ATTRIBUTES = frozenset(
    (
        "xmlns",
        "viewbox",
        "width",
        "height",
        "fill",
        "stroke",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "d",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "points",
        "transform",
        "focusable",
        "role",
        "aria-hidden",
        "class",
    ),
)


def _decode_svg_data_uri(source: str) -> bytes | None:
    normalized = source.strip()
    if len(normalized.encode("utf-8")) > MAX_TOOL_ICON_SOURCE_BYTES:
        return None
    separator_index = normalized.find(",")
    if separator_index < 0:
        return None
    raw_metadata = normalized[:separator_index]
    if not raw_metadata.startswith(SVG_DATA_URI_PREFIX):
        return None
    metadata = raw_metadata.lower()
    if metadata not in (
        SVG_DATA_URI_PREFIX,
        f"{SVG_DATA_URI_PREFIX};charset=utf-8",
        f"{SVG_DATA_URI_PREFIX};base64",
        f"{SVG_DATA_URI_PREFIX};charset=utf-8;base64",
    ):
        return None
    payload = normalized[separator_index + 1 :]
    if not payload:
        return None
    if not metadata.endswith(";base64") and not is_valid_percent_encoding(payload):
        return None
    try:
        decoded = (
            base64.b64decode(payload, validate=True)
            if metadata.endswith(";base64")
            else unquote(payload, encoding="utf-8", errors="strict").encode("utf-8")
        )
    except ValueError:
        return None
    if not decoded or len(decoded) > MAX_TOOL_ICON_SOURCE_BYTES:
        return None
    return decoded


def _validated_svg_source(value: JSONValue | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    decoded = _decode_svg_data_uri(normalized)
    if decoded is None:
        return None
    try:
        root = ElementTree.fromstring(decoded)
    except (DefusedXmlException, ElementTree.ParseError):
        return None
    if root.tag not in ("svg", SVG_XML_TAG):
        return None
    for element in root.iter():
        if element.tag.startswith("{") and not element.tag.startswith(
            "{http://www.w3.org/2000/svg}",
        ):
            return None
        tag_name = element.tag.rsplit("}", 1)[-1].lower()
        if tag_name not in ALLOWED_SVG_TAGS:
            return None
        for raw_name, raw_value in element.attrib.items():
            if raw_name.startswith("{"):
                return None
            attribute_name = raw_name.rsplit("}", 1)[-1].lower()
            normalized_value = raw_value.strip().lower()
            if attribute_name.startswith("on") or attribute_name not in ALLOWED_SVG_ATTRIBUTES:
                return None
            if "url(" in normalized_value or normalized_value.startswith(
                ("javascript:", "vbscript:")
            ):
                return None
    return normalized


def _first_valid_icon_source(definition: Mapping[str, JSONValue]) -> str | None:
    icons = definition.get("icons")
    if not isinstance(icons, list):
        return None
    for icon in icons:
        if not isinstance(icon, Mapping):
            continue
        source = _validated_svg_source(icon.get("src"))
        if source is not None:
            return source
    return None


def _collect_local_icons(definitions: Mapping[str, JSONDict]) -> dict[str, str]:
    collected: dict[str, str] = {}
    for tool_name, definition in definitions.items():
        source = _first_valid_icon_source(definition)
        if source is not None:
            collected[tool_name] = source
    return collected


def _collect_remote_icons(remote_tools: list[JSONDict]) -> dict[str, str]:
    collected: dict[str, str] = {}
    for tool in remote_tools:
        server_id = tool.get("server_id")
        tool_name = tool.get("name")
        if not isinstance(server_id, str) or not isinstance(tool_name, str):
            continue
        if not tool_name.strip():
            continue
        source = _first_valid_icon_source(tool)
        if source is None:
            continue
        try:
            canonical_name = encode_qualified_tool_name(server_id, tool_name.strip())
        except ValidationError:
            continue
        collected[canonical_name] = source
    return collected


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/mcp/tool-icons",
        response_model=WebuiToolIconCatalogResponse,
    )
    async def list_webui_tool_icons(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> WebuiToolIconCatalogResponse:
        definitions = api_context.dependencies.mcp_server.registration.tool_definitions(
            "internal_admin",
        )
        catalog = _collect_local_icons(definitions)
        remote_tools = await api_context.dependencies.mcp_remote.list_all_tools()
        catalog.update(_collect_remote_icons(remote_tools))
        return WebuiToolIconCatalogResponse(
            icons=[
                WebuiToolIcon(tool_name=tool_name, src=source)
                for tool_name, source in sorted(catalog.items())
            ],
        )
