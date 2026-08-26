"""SoAI - Shared schema primitives for browser action tool definitions [backend/mcp/tools/utility_tool_definitions/browser_action_schema_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)
from mcp.tools.utility_tool_definitions.browser_snapshot_schema_primitives import (
    build_action_inline_snapshot_output_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "BrowserActionSchemaPrimitives",
    "build_browser_action_schema_primitives",
)


@dataclass(frozen=True, slots=True)
class BrowserActionSchemaPrimitives:
    session_params: JSONDict
    element_property: JSONDict
    ref_property: JSONDict
    inline_snapshot_output_properties: JSONDict


def build_browser_action_schema_primitives() -> BrowserActionSchemaPrimitives:
    session_params = build_browser_session_param_properties()
    element_property: JSONDict = {
        "element": nullable_non_empty_string_schema(
            description="Optional human-readable element description.",
        ),
    }
    ref_property: JSONDict = {
        "ref": non_empty_string_schema(description="Element ref from browser_snapshot."),
    }
    return BrowserActionSchemaPrimitives(
        session_params=session_params,
        element_property=element_property,
        ref_property=ref_property,
        inline_snapshot_output_properties=build_action_inline_snapshot_output_properties(),
    )
