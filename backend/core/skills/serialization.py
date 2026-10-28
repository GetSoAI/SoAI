"""SoAI - Skill manifest persistence and public metadata projection [backend/core/skills/serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.skills.manifest import split_skill_manifest_source
from core.skills.manifest_fields import validate_skill_extension_fields
from core.skills.packages import validate_skill_resource_inventory
from core.skills.records import SkillManifest, SkillResource
from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.record_fields import (
    require_bool,
    require_int,
    require_json_object_list,
    require_non_empty_str,
)

__all__ = (
    "skill_manifest_payload",
    "restore_skill_manifest",
    "skill_resources_payload",
    "restore_skill_resources",
)


def skill_resources_payload(resources: tuple[SkillResource, ...]) -> list[JSONDict]:
    return [
        {
            "path": resource.path,
            "is_directory": resource.is_directory,
            "size_bytes": resource.size_bytes,
            "digest": resource.digest,
        }
        for resource in resources
    ]


def restore_skill_resources(
    payload: JSONValue, *, manifest_path: str = "SKILL.md"
) -> tuple[SkillResource, ...]:
    records = require_json_object_list(payload, label="Skill resources", build_error=StateError)
    resources: list[SkillResource] = []
    for record in records:
        if set(record) != {"path", "is_directory", "size_bytes", "digest"}:
            raise StateError("Skill resource metadata has invalid fields.")
        size = require_int(
            record.get("size_bytes"), label="Skill resource size", build_error=StateError
        )
        resources.append(
            SkillResource(
                require_non_empty_str(
                    record.get("path"), label="Skill path", build_error=StateError
                ),
                require_bool(
                    record.get("is_directory"), label="Skill directory", build_error=StateError
                ),
                size,
                require_non_empty_str(
                    record.get("digest"), label="Skill resource digest", build_error=StateError
                ),
            )
        )
    inventory = tuple(resources)
    validate_skill_resource_inventory(inventory, manifest_path=manifest_path)
    return inventory


def skill_manifest_payload(manifest: SkillManifest) -> JSONDict:
    payload: JSONDict = {
        "name": manifest.name,
        "description": manifest.description,
        "source": manifest.source,
        "instructions": manifest.instructions,
        "license": manifest.license,
        "compatibility": manifest.compatibility,
        "metadata": parse_json_dict(manifest.metadata_json, field="skill metadata"),
        "disable_model_invocation": manifest.disable_model_invocation,
        "user_invocable": manifest.user_invocable,
    }
    if manifest.extensions_json != "{}":
        payload["extensions"] = parse_json_dict(manifest.extensions_json, field="skill extensions")
    return payload


def restore_skill_manifest(payload: JSONDict, source_bytes: bytes) -> SkillManifest:
    source = payload.get("source")
    instructions = payload.get("instructions")
    license_text = payload.get("license")
    compatibility = payload.get("compatibility")
    metadata = payload.get("metadata")
    extensions = payload.get("extensions", {})
    if (
        not isinstance(source, str)
        or not isinstance(instructions, str)
        or not is_json_dict(metadata)
    ):
        raise StateError("Stored skill manifest metadata is invalid.")
    if not is_json_dict(extensions):
        raise StateError("Stored skill compatibility fields are invalid.")
    if (license_text is not None and not isinstance(license_text, str)) or (
        compatibility is not None and not isinstance(compatibility, str)
    ):
        raise StateError("Stored skill descriptive metadata is invalid.")
    try:
        extensions_json = validate_skill_extension_fields(extensions)
        retained_source, _frontmatter, retained_instructions = split_skill_manifest_source(
            source_bytes
        )
    except ValidationError as exception:
        raise StateError("Retained skill manifest source is invalid.") from exception
    if source != retained_source or instructions != retained_instructions:
        raise StateError("Stored skill instructions differ from the retained manifest.")
    return SkillManifest(
        name=require_non_empty_str(payload.get("name"), label="Skill name", build_error=StateError),
        description=require_non_empty_str(
            payload.get("description"), label="Skill description", build_error=StateError
        ),
        source=source,
        instructions=instructions,
        license=license_text,
        compatibility=compatibility,
        metadata_json=serialize_json_compact_stable_strict(metadata),
        disable_model_invocation=require_bool(
            payload.get("disable_model_invocation"),
            label="Skill automatic invocation",
            build_error=StateError,
        ),
        user_invocable=require_bool(
            payload.get("user_invocable"), label="Skill human invocation", build_error=StateError
        ),
        extensions_json=extensions_json,
    )
