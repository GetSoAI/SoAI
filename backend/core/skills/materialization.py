"""SoAI - Durable skill materialization identity and receipt metadata [backend/core/skills/materialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from core.conversations.input_claim import ConversationInputClaim
from core.errors.exceptions import StateError, ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.serialization.json import serialize_json_compact_stable
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.skills.execution import SkillExecutionIdentity
from core.skills.publication_layout import restore_skill_publication, skill_publication_payload
from core.skills.records import SkillPublicationLayout, SkillResource
from core.skills.selection import require_skill_id
from core.skills.serialization import skill_resources_payload
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_int, require_non_empty_str

__all__ = (
    "materialization_lock_path",
    "SkillMaterializationRequest",
    "SkillMaterializationReceipt",
    "restore_directory_identity",
)


def materialization_lock_path(
    plugin_directory: str, request_id: str, *, writer: bool = False
) -> str:
    return os.path.join(
        plugin_directory,
        ".locks",
        f"skill-materialize-{'writer-' if writer else ''}{require_mutation_request_id(request_id)}.lock",
    )


@dataclass(frozen=True, slots=True)
class SkillMaterializationRequest:
    identity: SkillExecutionIdentity
    root_input_id: str
    skill_id: str
    package_digest: str
    workspace_root: str
    workspace_identity: tuple[int, int]
    publication: SkillPublicationLayout | None = None
    profile_digest: str | None = None

    @property
    def manifest_path(self) -> str:
        return self.publication.manifest_path if self.publication else "SKILL.md"

    @property
    def publication_digest(self) -> str:
        return self.publication.digest if self.publication else self.package_digest

    @property
    def executable_paths(self) -> tuple[str, ...] | None:
        return self.publication.executable_paths if self.publication else None

    @property
    def operation_key(self) -> str:
        payload = self.payload()
        del payload["execution_token"]
        del payload["input_claim"]
        del payload["workspace_root"]
        del payload["workspace_identity"]
        return hashlib.sha256(serialize_json_compact_stable(payload).encode("utf-8")).hexdigest()

    def payload(self) -> JSONDict:
        payload: JSONDict = {
            "user_id": self.identity.user_id,
            "conv_id": self.identity.conv_id,
            "input_id": self.identity.input_id,
            "root_input_id": self.root_input_id,
            "turn_id": self.identity.turn_id,
            "execution_token": self.identity.execution_token,
            "input_claim": {
                "generation": self.identity.input_claim.generation,
                "owner": self.identity.input_claim.owner,
                "server_boot_id": self.identity.input_claim.server_boot_id,
            },
            "skill_id": self.skill_id,
            "package_digest": self.package_digest,
            "workspace_root": self.workspace_root,
            "workspace_identity": [str(part) for part in self.workspace_identity],
        }
        if self.publication is not None:
            if self.profile_digest is None:
                raise StateError("Collection materialization requires its captured profile digest.")
            payload["publication"] = skill_publication_payload(self.publication)
            payload["profile_digest"] = self.profile_digest
        return payload

    @classmethod
    def restore(cls, payload: JSONDict) -> SkillMaterializationRequest:
        expected = {
            "user_id",
            "conv_id",
            "input_id",
            "root_input_id",
            "turn_id",
            "execution_token",
            "input_claim",
            "skill_id",
            "package_digest",
            "workspace_root",
            "workspace_identity",
        }
        if set(payload) not in (expected, expected | {"publication", "profile_digest"}):
            raise StateError("Skill materialization request has invalid fields.")
        claim = payload["input_claim"]
        if not isinstance(claim, dict) or set(claim) != {"generation", "owner", "server_boot_id"}:
            raise StateError("Skill materialization input claim is invalid.")
        input_id = require_non_empty_str(
            payload["input_id"], label="Skill input", build_error=StateError
        )
        user_id = require_int(payload["user_id"], label="Skill owner", build_error=StateError)
        if user_id <= 0:
            raise StateError("Skill materialization owner is invalid.")
        workspace_root = require_non_empty_str(
            payload["workspace_root"], label="Skill workspace", build_error=StateError
        )
        if not os.path.isabs(workspace_root) or os.path.normpath(workspace_root) != workspace_root:
            raise StateError("Skill materialization workspace is not absolute and canonical.")
        try:
            skill_id = require_skill_id(payload["skill_id"])
        except ValidationError as exception:
            raise StateError("Persisted skill materialization identity is invalid.") from exception
        return cls(
            identity=SkillExecutionIdentity(
                user_id,
                require_non_empty_str(
                    payload["conv_id"], label="Skill conversation", build_error=StateError
                ),
                input_id,
                require_non_empty_str(
                    payload["turn_id"], label="Skill turn", build_error=StateError
                ),
                require_non_empty_str(
                    payload["execution_token"], label="Skill execution", build_error=StateError
                ),
                ConversationInputClaim(
                    input_id,
                    require_int(
                        claim["generation"], label="Skill input generation", build_error=StateError
                    ),
                    require_non_empty_str(
                        claim["owner"], label="Skill input owner", build_error=StateError
                    ),
                    require_non_empty_str(
                        claim["server_boot_id"], label="Skill input boot", build_error=StateError
                    ),
                ),
            ),
            root_input_id=require_non_empty_str(
                payload["root_input_id"], label="Skill snapshot root", build_error=StateError
            ),
            skill_id=skill_id,
            package_digest=require_canonical_sha256_hexdigest(
                require_non_empty_str(
                    payload["package_digest"], label="Skill package digest", build_error=StateError
                ),
                label="Skill package digest",
            ),
            workspace_root=workspace_root,
            workspace_identity=restore_directory_identity(payload["workspace_identity"]),
            publication=(
                restore_skill_publication(payload["publication"])
                if "publication" in payload
                else None
            ),
            profile_digest=(
                require_canonical_sha256_hexdigest(
                    require_non_empty_str(
                        payload["profile_digest"],
                        label="Skill profile digest",
                        build_error=StateError,
                    ),
                    label="Skill profile digest",
                )
                if "profile_digest" in payload
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class SkillMaterializationReceipt:
    request_id: str
    request: SkillMaterializationRequest
    resources: tuple[SkillResource, ...]
    staging_identity: tuple[int, int] | None
    publication_identity: tuple[int, int] | None
    terminal_status: str | None
    terminal_result: JSONDict | None
    execution_phase: str | None = None
    failure_cancelled: bool = False
    staging_cleanup_required: str | None = None
    recovery_required: bool = False

    @property
    def staging_name(self) -> str:
        return f".soai-skill-{require_mutation_request_id(self.request_id)}"

    @property
    def final_name(self) -> str:
        return f"skill-{require_mutation_request_id(self.request_id)}"

    def verification_arguments(
        self,
    ) -> tuple[
        str,
        tuple[int, int],
        str,
        tuple[int, int],
        tuple[SkillResource, ...],
        str,
        tuple[str, ...] | None,
    ]:
        if self.publication_identity is None:
            raise StateError("Materialization publication evidence is unavailable.")
        return (
            self.request.workspace_root,
            self.request.workspace_identity,
            self.final_name,
            self.publication_identity,
            self.resources,
            self.request.manifest_path,
            self.request.executable_paths,
        )

    def completed_result(self) -> JSONDict:
        result: JSONDict = {
            "skill_id": self.request.skill_id,
            "path": self.final_name,
            "resources": skill_resources_payload(self.resources),
            "materialized": True,
        }
        if self.request.publication is not None:
            skill_directory = self.request.manifest_path.rpartition("/")[0]
            result["path"] = (
                f"{self.final_name}/{skill_directory}" if skill_directory else self.final_name
            )
            plugin_root = self.request.publication.plugin_root
            result["source_root"] = (
                f"{self.final_name}/{plugin_root}" if plugin_root else self.final_name
            )
            result["manifest_path"] = f"{self.final_name}/{self.request.manifest_path}"
            result["layout_digest"] = self.request.publication.digest
        return result


def restore_directory_identity(value: JSONValue) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise StateError("Materialization directory identity is invalid.")
    parts: list[int] = []
    for part in value:
        if not isinstance(part, str):
            raise StateError("Materialization directory identity is invalid.")
        if (
            not part.isascii()
            or not part.isdecimal()
            or len(part) > 39
            or (len(part) > 1 and part.startswith("0"))
        ):
            raise StateError("Materialization directory identity is invalid.")
        number = int(part)
        if number >= 1 << 128:
            raise StateError("Materialization directory identity exceeds its platform range.")
        parts.append(number)
    return parts[0], parts[1]
