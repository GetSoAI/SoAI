"""SoAI - Automation disallowed tool config loader [backend/core/automation/automation_tool_blocklist.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_tool_validation import (
    normalize_automation_disallowed_unqualified_tools,
)
from core.config.protocols import ConfigProtocol
from core.types.json import JSONValue, is_json_value

__all__ = ("load_automation_disallowed_unqualified_tools",)

AUTOMATION_DISALLOWED_UNQUALIFIED_TOOLS_CONFIG_KEY: str = "AUTOMATION.DISALLOWED_UNQUALIFIED_TOOLS"


def load_automation_disallowed_unqualified_tools(config: ConfigProtocol) -> tuple[str, ...]:
    raw_value = config.get(AUTOMATION_DISALLOWED_UNQUALIFIED_TOOLS_CONFIG_KEY)
    json_value: JSONValue = raw_value if is_json_value(raw_value) else None
    return normalize_automation_disallowed_unqualified_tools(
        json_value,
        field_label=AUTOMATION_DISALLOWED_UNQUALIFIED_TOOLS_CONFIG_KEY,
    )
