"""SoAI - Immutable source tool compatibility guidance and restrictions [backend/core/skills/compatibility_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import read_regular_file_no_symlink
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.skills.manifest_sidecars import parse_skill_sidecar
from core.skills.records import SkillCompatibilityProfile, SkillManifest, SkillMember
from core.types.json import JSONDict, JSONValue, is_json_dict, is_str_list
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_bool, require_non_empty_str

__all__ = (
    "SkillCompatibilityTool",
    "load_skill_compatibility_catalog",
    "compile_skill_compatibility_profile",
    "restore_skill_compatibility_profile",
    "skill_requires_human_invocation",
)

_DISPOSITIONS = frozenset(
    {
        "adapt",
        "compose",
        "partial",
        "schema-only",
        "host-specific",
        "unverified-name",
        "dynamic",
        "exclude",
    }
)
_CANONICAL_TOOL_PATTERN = r"[a-z][a-z0-9_]*"


@dataclass(frozen=True, slots=True)
class SkillCompatibilityTool:
    harness: str
    name: str
    canonical_tools: tuple[str, ...]
    disposition: str
    guidance: str
    schema_variants: tuple[str, ...]
    surface: str


def load_skill_compatibility_catalog() -> tuple[SkillCompatibilityTool, ...]:
    path = os.path.join(os.path.dirname(__file__), "compatibility_catalog.json")
    content = read_regular_file_no_symlink(path, max_bytes=256 * 1024)
    if len(content) > 256 * 1024:
        raise StateError("Skill compatibility catalog exceeds its bounded size.")
    payload = parse_json_value(
        content, field="skill compatibility catalog", reject_duplicate_keys=True
    )
    if not isinstance(payload, list):
        raise StateError("Skill compatibility catalog must be an array.")
    identities: set[tuple[str, str, tuple[str, ...]]] = set()
    entries: list[SkillCompatibilityTool] = []
    for entry in payload:
        if not is_json_dict(entry):
            raise StateError("Skill compatibility catalog entry must be an object.")
        require_exact_json_fields(
            entry,
            allowed_fields={
                "harness",
                "name",
                "soai_tools",
                "status",
                "note",
                "schema_types",
                "surface",
            },
            label="Skill compatibility catalog",
        )
        harness, name, schemas, targets = (
            entry.get("harness"),
            entry.get("name"),
            entry.get("schema_types"),
            entry.get("soai_tools"),
        )
        if (
            not isinstance(harness, str)
            or not isinstance(name, str)
            or not is_str_list(schemas)
            or not is_str_list(targets)
        ):
            raise StateError("Skill compatibility catalog identity or targets are invalid.")
        disposition = require_non_empty_str(
            entry.get("status"), label="Skill compatibility disposition", build_error=StateError
        )
        if disposition not in _DISPOSITIONS:
            raise StateError("Skill compatibility catalog disposition is invalid.")
        identity = (harness, name, tuple(schemas))
        if identity in identities:
            raise StateError(
                "Skill compatibility catalog contains a duplicate qualified schema identity."
            )
        identities.add(identity)
        entries.append(
            SkillCompatibilityTool(
                harness,
                name,
                tuple(targets),
                disposition,
                require_non_empty_str(
                    entry.get("note"), label="Skill compatibility guidance", build_error=StateError
                ),
                tuple(schemas),
                require_non_empty_str(
                    entry.get("surface"),
                    label="Skill compatibility surface",
                    build_error=StateError,
                ),
            )
        )
    return tuple(entries)


def compile_skill_compatibility_profile(
    manifest: SkillManifest,
    source_root: str,
    catalog: tuple[SkillCompatibilityTool, ...],
    *,
    members: tuple[SkillMember, ...] = (),
    publication: JSONDict | None = None,
    aliases: tuple[str, ...] = (),
) -> SkillCompatibilityProfile:
    extensions = parse_json_dict(manifest.extensions_json, field="skill execution declarations")
    sidecar = parse_skill_sidecar(members)
    referenced: list[JSONValue] = []
    references_delegation = False
    for entry in catalog:
        if re.search(rf"(?<![\w]){re.escape(entry.name)}(?![\w])", manifest.source):
            references_delegation = (
                references_delegation or "subagent_spawn" in entry.canonical_tools
            )
            referenced.append(
                {
                    "source_harness": entry.harness,
                    "qualified_identity": entry.name,
                    "schema_variants": list(entry.schema_variants),
                    "canonical_tools": list(entry.canonical_tools),
                    "disposition": entry.disposition,
                    "guidance": entry.guidance,
                }
            )
    allowed, allowed_error = _compile_restrictions(extensions.get("allowed-tools"), catalog)
    disallowed, disallowed_error = _compile_restrictions(
        extensions.get("disallowed-tools"), catalog
    )
    host_guidance: list[str] = []
    if publication is not None:
        supporting = publication.get("supporting_digests")
        if isinstance(supporting, dict) and any(
            "/agents/" in f"/{path}" and path.endswith(".md") for path in supporting
        ):
            host_guidance.append(
                "Named agent presets are retained supporting Markdown resources, not registered workers. Read each required preset with skill_read(source_relative=true), then pass its instructions and permitted capabilities explicitly to subagent_spawn. Keep existing subagent records authoritative and collect results with subagent_observe."
            )
    if "hooks" in extensions:
        host_guidance.append(
            "Hooks are retained declarations. Import and activation never run hooks. Request any needed action explicitly through canonical SoAI tools."
        )
    if extensions.get("context") == "fork" or "agent" in extensions or references_delegation:
        host_guidance.append(
            "The parent delegates through subagent_spawn with explicit skill_ids and collects subagent_observe results. Pass the workspace and permitted capabilities explicitly; ordinary children do not inherit active skills. For continuing completed work, spawn a new child and include the predecessor's result and identity in context."
        )
        host_guidance.append(
            "Set subagent_spawn arguments explicitly: task, mode, tools, max_iterations, skill_ids and workspace_path. A role written in task text does not set these arguments. Use mode=plan and read-only tools for read-only reviews; use mode=execute when the assigned work needs authorized writes. Pass the captured skill IDs, authorized workspace and a finite iteration limit."
        )
        host_guidance.append(
            "A subagent_observe result with timed_out=true only means its observation deadline expired. Check subagent.status; while it is running, observe the same subagent again. Do not spawn duplicate work or claim failure merely because an observation timed out. Only terminal status establishes the worker outcome."
        )
        host_guidance.append(
            "Use subagent records as the sole worker roster. If file handoffs are required, publish one immutable Markdown file per message in an execution-scoped workspace directory through exclusive atomic file creation. Include sender, recipient, message ID, execution scope and reply reference. Verify identical content on duplicate publication and reject conflicts; ignore temporary files. The parent alone writes shared task summaries. Plan-mode children return structured observations instead of writing handoffs."
        )
    if "model" in extensions or "effort" in extensions:
        host_guidance.append(
            "Model and effort declarations are preferences. Keep the user's current model and billing configuration; explain any required change to the user."
        )
    if "!`" in manifest.instructions:
        host_guidance.append(
            "Dynamic shell substitution is not evaluated in skill text. Perform any needed command as a visible shell tool step under current approvals."
        )
    if "tools" in extensions:
        host_guidance.append(
            "The tools field declares capabilities and does not grant permissions or exempt approvals."
        )
    payload: JSONDict = {
        "source_root": source_root,
        "tool_guidance": referenced,
        "host_guidance": host_guidance,
        "allowed_tools": allowed,
        "disallowed_tools": disallowed or [],
        "activation_error": allowed_error or disallowed_error,
        "codex_sidecar": sidecar,
        "aliases": list(aliases),
    }
    if publication is not None:
        payload["publication"] = publication
    serialized = serialize_json_compact_stable_strict(payload)
    return SkillCompatibilityProfile(serialized, hashlib.sha256(serialized.encode()).hexdigest())


def _compile_restrictions(
    declaration: JSONValue, catalog: tuple[SkillCompatibilityTool, ...]
) -> tuple[list[str] | None, str | None]:
    if declaration is None:
        return None, None
    tokens = (
        re.split(r"[,\s]+", declaration.strip()) if isinstance(declaration, str) else declaration
    )
    if not is_str_list(tokens):
        return None, "The tool restriction must contain supported tool names."
    permitted: set[str] = set()
    for token in tokens:
        if token == "*":
            return None, "Wildcard tool restrictions require a verified compatibility profile."
        matches = [
            entry
            for entry in catalog
            if entry.name == token and entry.disposition in {"adapt", "compose"}
        ]
        alternatives = {entry.canonical_tools for entry in matches}
        if len(alternatives) > 1:
            return (
                None,
                "The tool restriction has ambiguous source harness or schema bindings. Use canonical SoAI tool names.",
            )
        targets = {target for entry in matches for target in entry.canonical_tools}
        if targets:
            permitted.update(targets)
        elif re.fullmatch(_CANONICAL_TOOL_PATTERN, token):
            permitted.add(token)
        else:
            return (
                None,
                "This skill uses unsupported restrictive tool syntax. Replace it with explicit canonical SoAI tool names before activation.",
            )
    return sorted(permitted), None


def restore_skill_compatibility_profile(
    content_json: str, digest: str
) -> SkillCompatibilityProfile:
    require_canonical_sha256_hexdigest(digest, label="Skill compatibility profile digest")
    if hashlib.sha256(content_json.encode()).hexdigest() != digest:
        raise StateError("Retained skill compatibility profile integrity verification failed.")
    payload = parse_json_dict(
        content_json, field="retained skill compatibility profile", reject_duplicate_keys=True
    )
    require_exact_json_fields(
        payload,
        allowed_fields={
            "source_root",
            "tool_guidance",
            "host_guidance",
            "allowed_tools",
            "disallowed_tools",
            "activation_error",
            "codex_sidecar",
            "publication",
            "aliases",
        },
        label="Retained skill compatibility profile",
    )
    if (
        not isinstance(payload.get("source_root"), str)
        or not isinstance(payload.get("tool_guidance"), list)
        or not is_str_list(payload.get("host_guidance"))
    ):
        raise StateError("Retained skill compatibility guidance is invalid.")
    if payload.get("allowed_tools") is not None and not is_str_list(payload["allowed_tools"]):
        raise StateError("Retained skill allowed-tool policy is invalid.")
    if not is_str_list(payload.get("disallowed_tools")):
        raise StateError("Retained skill disallowed-tool policy is invalid.")
    if payload.get("activation_error") is not None and not isinstance(
        payload["activation_error"], str
    ):
        raise ValidationError("Retained skill activation policy is invalid.")
    return SkillCompatibilityProfile(content_json, digest)


def skill_requires_human_invocation(
    manifest: SkillManifest, profile: SkillCompatibilityProfile | None
) -> bool:
    if manifest.disable_model_invocation or profile is None:
        return manifest.disable_model_invocation
    payload = parse_json_dict(profile.content_json, field="skill invocation policy")
    sidecar = payload.get("codex_sidecar")
    if not is_json_dict(sidecar):
        raise StateError("Retained Codex sidecar must be an object.")
    policy = sidecar.get("policy", {})
    if not is_json_dict(policy):
        raise StateError("Retained Codex invocation policy must be an object.")
    return not require_bool(
        policy.get("allow_implicit_invocation", True),
        label="Codex implicit invocation",
        build_error=StateError,
    )
