"""SoAI - Shared input schema primitives for browser tool definitions [backend/mcp/tools/utility_tool_definitions/browser_tool_input_schema_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_boolean_schema,
    nullable_enum_schema,
    nullable_integer_schema,
    nullable_non_empty_string_array_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_inline_snapshot_input_properties",
    "build_timeout_ms_property",
    "build_wait_until_property",
)


def build_inline_snapshot_input_properties() -> JSONDict:
    return {
        "include_snapshot": nullable_boolean_schema(
            description="If true, also return a browser_snapshot-style accessibility snapshot after the action stabilizes.",
        ),
        "snapshot_roles": nullable_non_empty_string_array_schema(
            description="Optional role filter to apply to the inline snapshot when include_snapshot=true.",
        ),
    }


def build_timeout_ms_property(*, min_ms: int, max_ms: int, description: str) -> JSONDict:
    return {
        "timeout_ms": nullable_integer_schema(
            minimum=min_ms,
            maximum=max_ms,
            description=str(description),
        ),
    }


def build_wait_until_property() -> JSONDict:
    return {
        "wait_until": nullable_enum_schema(
            ("load", "domcontentloaded", "networkidle"),
            description="Navigation readiness state. networkidle0/networkidle2 are not supported.",
        ),
    }
