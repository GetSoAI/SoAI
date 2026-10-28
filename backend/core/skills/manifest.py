"""SoAI - Bounded skill manifest parsing [backend/core/skills/manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.events import (
    AliasEvent,
    CollectionEndEvent,
    CollectionStartEvent,
    DocumentStartEvent,
    MappingStartEvent,
    ScalarEvent,
)

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.skills.errors import build_skill_error
from core.skills.limits import (
    MAX_COMPATIBILITY_CHARACTERS,
    MAX_DESCRIPTION_CHARACTERS,
    MAX_MANIFEST_BYTES,
    MAX_NAME_CHARACTERS,
    MAX_YAML_DEPTH,
    MAX_YAML_EVENTS,
)
from core.skills.manifest_fields import validate_skill_extension_fields
from core.skills.records import SkillManifest
from core.types.json import JSONDict, is_json_dict
from core.validation.record_fields import require_bool
from core.validation.strings import require_bounded_trimmed_text

__all__ = (
    "SKILL_NAME_PATTERN_TEXT",
    "parse_skill_manifest",
    "split_skill_manifest_source",
    "parse_skill_yaml_mapping",
)


SKILL_NAME_PATTERN_TEXT = r"[a-z0-9]+(?:-[a-z0-9]+)*"


def split_skill_manifest_source(content: bytes) -> tuple[str, str, str]:
    if len(content) > MAX_MANIFEST_BYTES:
        raise build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field="manifest_bytes",
            measured=len(content),
            limit=MAX_MANIFEST_BYTES,
        )
    try:
        source = content.decode("utf-8-sig")
    except UnicodeDecodeError as exception:
        raise ValidationError("SKILL.md must contain UTF-8 text.") from exception
    if "\x00" in source:
        raise ValidationError("SKILL.md must not contain NUL characters.")
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValidationError("SKILL.md must begin with YAML frontmatter delimited by ---.")
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].rstrip("\r\n") == "---"),
        None,
    )
    if closing is None:
        raise ValidationError("SKILL.md is missing its closing frontmatter delimiter.")
    frontmatter = "".join(lines[1:closing])
    return source, frontmatter, "".join(lines[closing + 1 :])


def parse_skill_manifest(content: bytes, *, directory_name: str | None = None) -> SkillManifest:
    try:
        source, frontmatter, instructions = split_skill_manifest_source(content)
        payload = parse_skill_yaml_mapping(frontmatter, source_line_offset=1)
    except ValidationError as exception:
        if exception.details is not None and exception.details.get("reason") in {
            "resource_limit",
            "manifest_format",
        }:
            raise
        raise build_skill_error("skill_invalid_package", reason="manifest_format") from exception
    try:
        extensions_json = validate_skill_extension_fields(payload)
    except ValidationError as exception:
        field = exception.details.get("field") if exception.details is not None else None
        raise build_skill_error(
            "skill_invalid_package",
            reason="invalid_field",
            field=field if isinstance(field, str) else None,
        ) from exception
    if directory_name is not None:
        if "name" not in payload:
            payload["name"] = directory_name
        if "description" not in payload:
            payload["description"] = next(
                (line.strip() for line in instructions.splitlines() if line.strip()), ""
            )
    name = _bounded_field(payload, "name", MAX_NAME_CHARACTERS)
    if name != payload["name"] or re.fullmatch(SKILL_NAME_PATTERN_TEXT, name) is None:
        raise build_skill_error("skill_invalid_package", reason="invalid_field", field="name")
    description = _bounded_field(payload, "description", MAX_DESCRIPTION_CHARACTERS)
    license_text = payload.get("license")
    if license_text is not None and not isinstance(license_text, str):
        raise build_skill_error("skill_invalid_package", reason="invalid_field", field="license")
    if "license" in payload and license_text is None:
        raise build_skill_error("skill_invalid_package", reason="invalid_field", field="license")
    compatibility = (
        _bounded_field(payload, "compatibility", MAX_COMPATIBILITY_CHARACTERS)
        if "compatibility" in payload
        else None
    )
    metadata = payload.get("metadata", {})
    if not is_json_dict(metadata):
        raise build_skill_error("skill_invalid_package", reason="invalid_field", field="metadata")
    return SkillManifest(
        name=name,
        description=description,
        source=source,
        instructions=instructions,
        license=license_text,
        compatibility=compatibility,
        metadata_json=serialize_json_compact_stable_strict(metadata),
        disable_model_invocation=_bool_field(payload, "disable-model-invocation", False),
        user_invocable=_bool_field(payload, "user-invocable", True),
        extensions_json=extensions_json,
    )


def _bounded_field(payload: JSONDict, field: str, maximum: int) -> str:
    try:
        return require_bounded_trimmed_text(
            payload.get(field),
            type_message=f"Skill {field} must be a string.",
            empty_message=f"Skill {field} must not be blank.",
            max_length=maximum,
            max_length_message=f"Skill {field} must contain at most {maximum} characters.",
        )
    except ValidationError as exception:
        raise build_skill_error(
            "skill_invalid_package", reason="invalid_field", field=field
        ) from exception


def _bool_field(payload: JSONDict, field: str, default: bool) -> bool:
    try:
        return require_bool(payload.get(field, default), label=field, build_error=ValidationError)
    except ValidationError as exception:
        raise build_skill_error(
            "skill_invalid_package", reason="invalid_field", field=field
        ) from exception


def parse_skill_yaml_mapping(source: str, *, source_line_offset: int = 0) -> JSONDict:
    parser = YAML(typ="safe", pure=True)
    parser.allow_duplicate_keys = False
    depth = 0
    documents = 0
    mapping_positions: list[int | None] = []
    try:
        for count, event in enumerate(parser.parse(source), start=1):
            if count > MAX_YAML_EVENTS:
                raise build_skill_error(
                    "skill_invalid_package",
                    reason="resource_limit",
                    field="yaml_events",
                    measured=count,
                    limit=MAX_YAML_EVENTS,
                )
            if isinstance(event, AliasEvent):
                raise ValidationError("Skill frontmatter must not contain YAML aliases.")
            if isinstance(event, CollectionStartEvent | ScalarEvent):
                if event.anchor is not None or event.tag is not None:
                    raise ValidationError(
                        "Skill frontmatter must not contain YAML anchors or tags."
                    )
                position = mapping_positions[-1] if mapping_positions else None
                if position is not None:
                    is_merge_key = (
                        position % 2 == 0 and isinstance(event, ScalarEvent) and event.value == "<<"
                    )
                    if is_merge_key:
                        raise ValidationError("Skill frontmatter must not contain YAML merge keys.")
                    mapping_positions[-1] = position + 1
            if isinstance(event, CollectionStartEvent):
                mapping_positions.append(0 if isinstance(event, MappingStartEvent) else None)
                depth += 1
                if depth > MAX_YAML_DEPTH:
                    raise build_skill_error(
                        "skill_invalid_package",
                        reason="resource_limit",
                        field="yaml_depth",
                        measured=depth,
                        limit=MAX_YAML_DEPTH,
                    )
            elif isinstance(event, CollectionEndEvent):
                mapping_positions.pop()
                depth -= 1
            elif isinstance(event, DocumentStartEvent):
                documents += 1
        if documents != 1:
            raise ValidationError("Skill frontmatter must contain exactly one mapping document.")
        payload = parser.load(source)
    except MarkedYAMLError as exception:
        mark = exception.problem_mark or exception.context_mark
        raise build_skill_error(
            "skill_invalid_package",
            reason="manifest_format",
            source_position=(
                (mark.line + source_line_offset + 1, mark.column + 1) if mark is not None else None
            ),
        ) from exception
    except (YAMLError, ValueError, OverflowError) as exception:
        raise ValidationError(
            "Skill frontmatter is invalid YAML or contains duplicate keys."
        ) from exception
    if not is_json_dict(payload):
        raise ValidationError(
            "Skill frontmatter must be a mapping with string keys and plain values."
        )
    try:
        serialize_json_compact_stable_strict(payload)
    except (ValueError, OverflowError) as exception:
        raise ValidationError(
            "Skill frontmatter exceeds supported JSON numeric representation limits."
        ) from exception
    return payload
