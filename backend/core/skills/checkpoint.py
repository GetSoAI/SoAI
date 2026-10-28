"""SoAI - Typed skill activation checkpoint serialization and restoration [backend/core/skills/checkpoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.skills.execution import SkillExecutionContext, SkillInvocationBinding, SkillSnapshot
from core.skills.limits import MAX_INSTALLED_SKILLS
from core.skills.selection import require_skill_id
from core.types.json import JSONDict
from core.validation.object_fields import require_exact_json_fields
from core.validation.strings import require_canonical_trimmed_json_text

__all__ = ("SkillActivationCheckpoint",)


@dataclass(frozen=True, slots=True)
class SkillActivationCheckpoint:
    snapshot_input_id: str
    active_skills: tuple[tuple[str, str], ...]
    invocations: tuple[SkillInvocationBinding, ...] = ()

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.snapshot_input_id, error_message="Skill checkpoint input identity is invalid."
        )
        if len(self.active_skills) > MAX_INSTALLED_SKILLS:
            raise StateError("Skill activation checkpoint exceeds the selection limit.")
        seen: set[str] = set()
        for skill_id, digest in self.active_skills:
            require_skill_id(skill_id)
            require_canonical_sha256_hexdigest(digest, label="Skill activation digest")
            if skill_id in seen:
                raise StateError("Skill activation checkpoint contains duplicate identities.")
            seen.add(skill_id)
        if len({invocation.call_id for invocation in self.invocations}) != len(self.invocations):
            raise StateError("Skill checkpoint invocation identities must be unique.")
        for invocation in self.invocations:
            if invocation.skill_id not in seen or not invocation.call_id:
                raise StateError("Skill checkpoint invocation must belong to an active skill.")

    @classmethod
    def from_execution(cls, context: SkillExecutionContext) -> SkillActivationCheckpoint:
        available = {skill.skill_id: skill for skill in context.snapshot.available}
        return cls(
            snapshot_input_id=context.snapshot.input_id,
            active_skills=tuple(
                (skill_id, available[skill_id].package_digest)
                for skill_id in context.active_skill_ids
            ),
            invocations=context.invocations,
        )

    def restore_execution(self, snapshot: SkillSnapshot) -> SkillExecutionContext:
        if snapshot.input_id != self.snapshot_input_id:
            raise StateError("Skill checkpoint belongs to another admitted input.")
        available = {skill.skill_id: skill.package_digest for skill in snapshot.available}
        if any(available.get(skill_id) != digest for skill_id, digest in self.active_skills):
            raise StateError("Skill activation checkpoint differs from retained availability.")
        return SkillExecutionContext(
            snapshot=snapshot,
            active_skill_ids=tuple(skill_id for skill_id, _digest in self.active_skills),
            invocations=self.invocations,
        )

    def serialize(self) -> str:
        payload: JSONDict = {
            "snapshot_input_id": self.snapshot_input_id,
            "active_skills": [
                {"skill_id": skill_id, "package_digest": digest}
                for skill_id, digest in self.active_skills
            ],
        }
        if self.invocations:
            payload["invocations"] = [
                {
                    "skill_id": invocation.skill_id,
                    "call_id": invocation.call_id,
                    "arguments": invocation.arguments,
                }
                for invocation in self.invocations
            ]
        return serialize_json_compact_stable_strict(payload)

    @classmethod
    def deserialize(cls, serialized: str) -> SkillActivationCheckpoint:
        payload = parse_json_dict(
            serialized, field="skill activation checkpoint", reject_duplicate_keys=True
        )
        require_exact_json_fields(
            payload,
            allowed_fields={"snapshot_input_id", "active_skills", "invocations"},
            label="Skill activation checkpoint",
        )
        input_id = require_canonical_trimmed_json_text(
            payload.get("snapshot_input_id"),
            error_message="Skill checkpoint input identity is invalid.",
        )
        active = payload.get("active_skills")
        if not isinstance(active, list) or len(active) > MAX_INSTALLED_SKILLS:
            raise ValidationError("Skill checkpoint requires a bounded activation list.")
        activations: list[tuple[str, str]] = []
        for entry in active:
            if not isinstance(entry, dict):
                raise ValidationError("Skill checkpoint activation must be an object.")
            require_exact_json_fields(
                entry,
                allowed_fields={"skill_id", "package_digest"},
                label="Skill checkpoint activation",
            )
            digest = entry.get("package_digest")
            if not isinstance(digest, str):
                raise ValidationError("Skill checkpoint activation digest is missing.")
            activations.append((require_skill_id(entry.get("skill_id")), digest))
        invocation_values = payload.get("invocations", [])
        if not isinstance(invocation_values, list):
            raise ValidationError("Skill checkpoint invocations must be an array.")
        invocations: list[SkillInvocationBinding] = []
        for entry in invocation_values:
            if not isinstance(entry, dict):
                raise ValidationError("Skill checkpoint invocation must be an object.")
            require_exact_json_fields(
                entry,
                allowed_fields={"skill_id", "call_id", "arguments"},
                label="Skill checkpoint invocation",
            )
            arguments = entry.get("arguments")
            if not isinstance(arguments, str):
                raise ValidationError("Skill checkpoint invocation arguments must be a string.")
            invocations.append(
                SkillInvocationBinding(
                    require_skill_id(entry.get("skill_id")),
                    require_canonical_trimmed_json_text(
                        entry.get("call_id"),
                        error_message="Skill invocation call identity is invalid.",
                    ),
                    arguments,
                )
            )
        return cls(input_id, tuple(activations), tuple(invocations))
