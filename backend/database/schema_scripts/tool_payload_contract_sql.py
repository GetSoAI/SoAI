"""SoAI - Database schema SQL for tool payload contracts [backend/database/schema_scripts/tool_payload_contract_sql.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "assistant_timeline_tool_payload_invalid_condition",
    "live_tool_payload_invalid_condition",
)


def _tool_payload_required_condition() -> str:
    return """
json_type(NEW.payload_json, '$.tool') IS NOT 'object'
  OR length(trim(COALESCE(json_extract(NEW.payload_json, '$.tool.call_id'), ''))) = 0
  OR length(trim(COALESCE(json_extract(NEW.payload_json, '$.tool.tool_name'), ''))) = 0
  OR length(trim(COALESCE(json_extract(NEW.payload_json, '$.tool.status'), ''))) = 0
  OR json_type(NEW.payload_json, '$.tool.sequence_index') IS NOT 'integer'
  OR json_extract(NEW.payload_json, '$.tool.sequence_index') < 0
  OR json_type(NEW.payload_json, '$.tool.message_index') IS NOT 'integer'
  OR json_extract(NEW.payload_json, '$.tool.message_index') < 0
  OR json_type(NEW.payload_json, '$.tool.content_index_before') IS NOT 'integer'
  OR json_extract(NEW.payload_json, '$.tool.content_index_before') < 0
  OR json_type(NEW.payload_json, '$.tool.thinking_index_before') IS NOT 'integer'
  OR json_extract(NEW.payload_json, '$.tool.thinking_index_before') < 0
  OR (
      json_type(NEW.payload_json, '$.tool.collapsed') IS NOT 'true'
      AND json_type(NEW.payload_json, '$.tool.collapsed') IS NOT 'false'
  )
""".strip()


def assistant_timeline_tool_payload_invalid_condition() -> str:
    return _tool_payload_required_condition()


def live_tool_payload_invalid_condition() -> str:
    return (
        "json_extract(NEW.payload_json, '$.tool.call_id') != NEW.call_id\n"
        f"  OR {_tool_payload_required_condition()}"
    )
