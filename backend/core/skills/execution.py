"""SoAI - Immutable admitted skill availability and execution activation [backend/core/skills/execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace

from core.conversations.input_claim import ConversationInputClaim
from core.errors.exceptions import StateError, ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.skills.compatibility_profiles import skill_requires_human_invocation
from core.skills.errors import build_skill_error
from core.skills.records import SkillCompatibilityProfile, SkillManifest, SkillResource

__all__ = (
    "AvailableSkill",
    "SkillSnapshot",
    "SkillExecutionContext",
    "SkillExecutionIdentity",
    "propose_skill_activation",
    "SkillInvocationBinding",
)


@dataclass(frozen=True, slots=True)
class SkillExecutionIdentity:
    user_id: int
    conv_id: str
    input_id: str
    turn_id: str
    execution_token: str
    input_claim: ConversationInputClaim


@dataclass(frozen=True, slots=True)
class AvailableSkill:
    skill_id: str
    package_digest: str
    manifest: SkillManifest
    resources: tuple[SkillResource, ...] = ()
    profile: SkillCompatibilityProfile | None = None


@dataclass(frozen=True, slots=True)
class SkillSnapshot:
    user_id: int
    conv_id: str
    input_id: str
    root_input_id: str
    selection_revision: int
    available: tuple[AvailableSkill, ...]
    explicit_skill_ids: tuple[str, ...]
    explicit_arguments: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        available_ids = tuple(skill.skill_id for skill in self.available)
        if len(set(available_ids)) != len(available_ids):
            raise StateError("Skill snapshot contains duplicate installation identities.")
        if len(set(self.explicit_skill_ids)) != len(self.explicit_skill_ids):
            raise StateError("Skill snapshot contains duplicate human invocation identities.")
        if not set(self.explicit_skill_ids).issubset(available_ids):
            raise StateError("Skill snapshot human invocation is outside admitted availability.")
        if any(
            not skill.manifest.user_invocable and skill.skill_id in self.explicit_skill_ids
            for skill in self.available
        ):
            raise StateError("Skill snapshot contains a prohibited human invocation.")
        argument_ids = [skill_id for skill_id, _arguments in self.explicit_arguments]
        if len(set(argument_ids)) != len(argument_ids) or not set(argument_ids).issubset(
            self.explicit_skill_ids
        ):
            raise StateError("Skill arguments must belong to distinct admitted human invocations.")


@dataclass(frozen=True, slots=True)
class SkillInvocationBinding:
    skill_id: str
    call_id: str
    arguments: str


@dataclass(frozen=True, slots=True)
class SkillExecutionContext:
    snapshot: SkillSnapshot
    active_skill_ids: tuple[str, ...] = ()
    invocations: tuple[SkillInvocationBinding, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.active_skill_ids)) != len(self.active_skill_ids):
            raise StateError("Skill execution contains duplicate activations.")
        available_ids = {skill.skill_id for skill in self.snapshot.available}
        if not set(self.active_skill_ids).issubset(available_ids):
            raise StateError("Skill execution activation is outside admitted availability.")
        if any(
            skill.skill_id in self.active_skill_ids
            and skill_requires_human_invocation(skill.manifest, skill.profile)
            and skill.skill_id not in self.snapshot.explicit_skill_ids
            for skill in self.snapshot.available
        ):
            raise StateError("Skill execution lacks the required human invocation.")
        if len({invocation.call_id for invocation in self.invocations}) != len(self.invocations):
            raise StateError("Skill execution invocation call identities must be unique.")
        for invocation in self.invocations:
            if not invocation.call_id or invocation.skill_id not in self.active_skill_ids:
                raise StateError("Skill invocation lacks an active skill or call identity.")
            human_arguments = dict(self.snapshot.explicit_arguments).get(invocation.skill_id)
            if human_arguments is not None and human_arguments != invocation.arguments:
                raise StateError("Skill invocation replaced admitted human arguments.")

    def require_owner(self, *, user_id: int, conv_id: str) -> None:
        if self.snapshot.user_id != user_id or self.snapshot.conv_id != conv_id:
            raise StateError("Skill execution context belongs to another conversation owner.")


def propose_skill_activation(
    context: SkillExecutionContext,
    skill_id: str,
    *,
    arguments: str | None = None,
    call_id: str | None = None,
) -> SkillExecutionContext:
    skill = next((item for item in context.snapshot.available if item.skill_id == skill_id), None)
    if skill is None:
        raise ValidationError("Skill is not available in this execution.")
    if (
        skill_requires_human_invocation(skill.manifest, skill.profile)
        and skill_id not in context.snapshot.explicit_skill_ids
    ):
        raise ValidationError("This skill requires an explicit human invocation in this execution.")
    if skill.profile is not None:
        profile = parse_json_dict(skill.profile.content_json, field="skill activation profile")
        if profile.get("activation_error") is not None:
            raise build_skill_error(
                "skill_invocation_unavailable", reason="restriction_unsupported"
            )
    elif any(
        field in parse_json_dict(skill.manifest.extensions_json)
        for field in ("allowed-tools", "disallowed-tools")
    ):
        raise build_skill_error("skill_invocation_unavailable", reason="restriction_unsupported")
    human_arguments = dict(context.snapshot.explicit_arguments).get(skill_id)
    if human_arguments is not None and arguments is not None and arguments != human_arguments:
        raise build_skill_error("skill_invocation_unavailable", reason="argument_conflict")
    effective_arguments = human_arguments if human_arguments is not None else arguments
    existing = next(
        (invocation for invocation in context.invocations if invocation.call_id == call_id), None
    )
    if existing is not None:
        if existing.skill_id != skill_id or (
            effective_arguments is not None and existing.arguments != effective_arguments
        ):
            raise build_skill_error("skill_invocation_unavailable", reason="argument_conflict")
        return context
    invocations = context.invocations
    if arguments is not None or call_id is not None:
        if not call_id:
            raise StateError("Skill invocation arguments require a durable tool call identity.")
        invocations = (
            *invocations,
            SkillInvocationBinding(skill_id, call_id, effective_arguments or ""),
        )
    active = (
        context.active_skill_ids
        if skill_id in context.active_skill_ids
        else (*context.active_skill_ids, skill_id)
    )
    if active == context.active_skill_ids and invocations == context.invocations:
        return context
    return replace(context, active_skill_ids=active, invocations=invocations)
