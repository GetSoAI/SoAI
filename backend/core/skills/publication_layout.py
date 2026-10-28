"""SoAI - Immutable collection source mappings and publication integrity [backend/core/skills/publication_layout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.archives.constants import validate_member_name
from core.archives.errors import ArchivePathTraversalError
from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.skills.packages import complete_skill_inventory, validate_skill_resource_inventory
from core.skills.records import SkillCompatibilityProfile, SkillMember, SkillPublicationLayout
from core.types.json import JSONDict, JSONValue, is_json_dict, is_str_list
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_non_empty_str

__all__ = (
    "map_skill_publication",
    "skill_publication_payload",
    "restore_skill_publication",
    "skill_profile_publication",
)


def map_skill_publication(
    source_root: str, members: tuple[SkillMember, ...], supporting: tuple[SkillMember, ...]
) -> tuple[SkillMember, ...]:
    output = {
        f"{source_root}/{member.path}" if source_root else member.path: member for member in members
    }
    mapped = {path: replace(member, path=path) for path, member in output.items()}
    for member in supporting:
        previous = mapped.get(member.path)
        if previous is not None and previous != member:
            raise StateError("Skill publication has conflicting source bindings.")
        mapped[member.path] = member
    inventory = complete_skill_inventory(mapped)
    validate_skill_resource_inventory(
        tuple(member.resource for member in inventory),
        manifest_path=f"{source_root}/SKILL.md" if source_root else "SKILL.md",
    )
    return inventory


def skill_publication_payload(layout: SkillPublicationLayout) -> JSONDict:
    return {
        "manifest_path": layout.manifest_path,
        "digest": layout.digest,
        "supporting_digests": dict(layout.supporting_digests),
        "executable_paths": list(layout.executable_paths),
        "plugin_root": layout.plugin_root,
    }


def restore_skill_publication(value: JSONValue) -> SkillPublicationLayout:
    if not is_json_dict(value):
        raise StateError("Skill publication layout must be an object.")
    require_exact_json_fields(
        value,
        allowed_fields={
            "manifest_path",
            "digest",
            "supporting_digests",
            "executable_paths",
            "plugin_root",
        },
        label="Skill publication layout",
    )
    path = require_non_empty_str(
        value.get("manifest_path"), label="Skill publication manifest", build_error=StateError
    )
    supporting = value.get("supporting_digests")
    if not is_json_dict(supporting):
        raise StateError("Skill publication support bindings must be an object.")
    executable_paths = value.get("executable_paths")
    if not is_str_list(executable_paths) or executable_paths != sorted(set(executable_paths)):
        raise StateError("Skill publication executable paths must be distinct and canonical.")
    bindings: list[tuple[str, str]] = []
    plugin_root = value.get("plugin_root", "")
    if not isinstance(plugin_root, str):
        raise StateError("Skill publication plugin root must be a string.")
    try:
        validate_member_name(path)
        if plugin_root:
            validate_member_name(plugin_root)
            if "\\" in plugin_root or not path.startswith(f"{plugin_root}/"):
                raise StateError("Skill publication plugin root must contain its manifest.")
        if path.rsplit("/", 1)[-1] != "SKILL.md" or "\\" in path:
            raise StateError("Skill publication manifest path is invalid.")
        for support_path, digest in sorted(supporting.items()):
            validate_member_name(support_path)
            if "\\" in support_path:
                raise StateError("Skill publication support path is invalid.")
            bindings.append(
                (
                    support_path,
                    require_canonical_sha256_hexdigest(
                        require_non_empty_str(
                            digest, label="Skill support digest", build_error=StateError
                        ),
                        label="Skill support digest",
                    ),
                )
            )
    except ArchivePathTraversalError as exception:
        raise StateError("Skill publication contains an unsafe source path.") from exception
    return SkillPublicationLayout(
        path,
        require_canonical_sha256_hexdigest(
            require_non_empty_str(
                value.get("digest"), label="Skill publication digest", build_error=StateError
            ),
            label="Skill publication digest",
        ),
        tuple(bindings),
        tuple(executable_paths),
        plugin_root,
    )


def skill_profile_publication(
    profile: SkillCompatibilityProfile | None,
) -> SkillPublicationLayout | None:
    if profile is None:
        return None
    payload = parse_json_dict(profile.content_json, field="Skill publication profile")
    value = payload.get("publication")
    if value is None:
        return None
    layout = restore_skill_publication(value)
    source_root = payload.get("source_root")
    expected = f"{source_root}/SKILL.md" if source_root else "SKILL.md"
    if layout.manifest_path != expected:
        raise StateError("Skill publication differs from its captured source root.")
    return layout
