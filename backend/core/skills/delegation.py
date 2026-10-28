"""SoAI - Explicit captured skill instructions for delegated tasks [backend/core/skills/delegation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.errors.exceptions import StateError, ValidationError
from core.skills.execution import SkillExecutionContext
from core.skills.prompt_projection import project_skill_context

__all__ = ("build_delegated_skill_instructions",)


def build_delegated_skill_instructions(
    context: SkillExecutionContext | None, skill_ids: tuple[str, ...]
) -> str | None:
    if not skill_ids:
        return None
    if (
        context is None
        or len(set(skill_ids)) != len(skill_ids)
        or not set(skill_ids).issubset(context.active_skill_ids)
    ):
        raise ValidationError(
            "Delegated skills must be distinct active skills in the parent execution."
        )
    snapshot = replace(
        context.snapshot,
        available=tuple(
            skill for skill in context.snapshot.available if skill.skill_id in skill_ids
        ),
        explicit_skill_ids=tuple(
            skill_id for skill_id in context.snapshot.explicit_skill_ids if skill_id in skill_ids
        ),
        explicit_arguments=tuple(
            binding for binding in context.snapshot.explicit_arguments if binding[0] in skill_ids
        ),
    )
    delegated = replace(
        context,
        snapshot=snapshot,
        active_skill_ids=skill_ids,
        invocations=tuple(
            binding for binding in context.invocations if binding.skill_id in skill_ids
        ),
    )
    messages = project_skill_context([], delegated, automatic_loading_available=False)
    content = messages[0].get("content") if len(messages) == 1 else None
    if not isinstance(content, str):
        raise StateError("Delegated skill instructions could not be projected.")
    return (
        "Delegated worker scope: Complete only the parent's assigned task. The parent owns scheduling, "
        "coordination and reviews. Apply these skills to that assignment without restarting their "
        "orchestration recipes or requesting nested subagent control. Return the observed result and "
        f"any remaining work.\n\n{content}"
    )
