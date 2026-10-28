"""SoAI - Pure active skill restriction intersection and tool corrections [backend/core/skills/execution_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.serialization.json_parsing import parse_json_dict
from core.skills.errors import build_skill_error
from core.skills.execution import SkillExecutionContext
from core.types.json import JSONValue

__all__ = (
    "skill_tool_is_permitted",
    "require_skill_tool_permission",
    "skill_foreign_tool_guidance",
)

SKILL_PACKAGE_READ_TOOL_NAME = "skill_read"


def skill_tool_is_permitted(context: SkillExecutionContext | None, tool_name: str) -> bool:
    if context is None:
        return True
    for skill in context.snapshot.available:
        if skill.skill_id not in context.active_skill_ids:
            continue
        if skill.profile is None:
            declarations = parse_json_dict(
                skill.manifest.extensions_json, field="skill declarations"
            )
            if "allowed-tools" in declarations or "disallowed-tools" in declarations:
                return False
            continue
        policy = parse_json_dict(skill.profile.content_json, field="active skill policy")
        if policy.get("activation_error") is not None:
            return False
        allowed = policy["allowed_tools"]
        disallowed = policy["disallowed_tools"]
        if (
            isinstance(allowed, list)
            and tool_name not in allowed
            and tool_name != SKILL_PACKAGE_READ_TOOL_NAME
        ) or (isinstance(disallowed, list) and tool_name in disallowed):
            return False
    return True


def require_skill_tool_permission(context: SkillExecutionContext | None, tool_name: str) -> None:
    if not skill_tool_is_permitted(context, tool_name):
        raise build_skill_error("skill_invocation_unavailable", reason="tool_restricted")


def skill_foreign_tool_guidance(
    context: SkillExecutionContext | None, tool_name: str
) -> list[JSONValue]:
    if context is None:
        return []
    guidance: list[JSONValue] = []
    seen: set[str] = set()
    for skill in context.snapshot.available:
        if skill.skill_id not in context.active_skill_ids or skill.profile is None:
            continue
        profile = parse_json_dict(skill.profile.content_json, field="active skill guidance")
        entries = profile.get("tool_guidance")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("qualified_identity") == tool_name:
                identity = f"{entry.get('source_harness')}:{tool_name}"
                if identity not in seen:
                    seen.add(identity)
                    guidance.append(entry)
    return guidance
