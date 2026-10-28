"""SoAI - Bounded Codex sidecar policy and prerequisite declarations [backend/core/skills/manifest_sidecars.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.archives.constants import validate_member_name
from core.archives.errors import ArchivePathTraversalError
from core.errors.exceptions import ValidationError
from core.skills.limits import MAX_MANIFEST_BYTES
from core.skills.manifest import parse_skill_yaml_mapping
from core.skills.records import SkillMember
from core.types.json import JSONDict, is_json_dict, is_str_list
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_bool
from core.validation.strings import require_bounded_trimmed_text

__all__ = ("parse_skill_sidecar",)


def parse_skill_sidecar(members: tuple[SkillMember, ...]) -> JSONDict:
    member = next((member for member in members if member.path == "agents/openai.yaml"), None)
    if member is None:
        return {}
    if member.is_directory or len(member.content) > MAX_MANIFEST_BYTES:
        raise ValidationError("agents/openai.yaml must be a bounded regular YAML file.")
    try:
        payload = parse_skill_yaml_mapping(member.content.decode("utf-8-sig"))
    except UnicodeDecodeError as exception:
        raise ValidationError("agents/openai.yaml must contain UTF-8 text.") from exception
    require_exact_json_fields(
        payload, allowed_fields={"interface", "policy", "dependencies"}, label="Codex skill sidecar"
    )
    interface = payload.get("interface", {})
    if not is_json_dict(interface):
        raise ValidationError("Codex skill interface must be an object.")
    require_exact_json_fields(
        interface,
        allowed_fields={
            "display_name",
            "short_description",
            "icon_small",
            "icon_large",
            "brand_color",
            "default_prompt",
        },
        label="Codex skill interface",
    )
    for field, value in interface.items():
        text = require_bounded_trimmed_text(
            value,
            type_message=f"Codex interface {field} must be text.",
            empty_message=f"Codex interface {field} must not be blank.",
            max_length=MAX_MANIFEST_BYTES,
            max_length_message=f"Codex interface {field} exceeds its text limit.",
        )
        if field in {"icon_small", "icon_large"}:
            path = text.removeprefix("./")
            try:
                validate_member_name(path)
            except ArchivePathTraversalError as exception:
                raise ValidationError(
                    f"Codex interface {field} contains an unsafe resource path."
                ) from exception
            if (
                "\\" in path
                or ":" in path
                or not any(
                    resource.path == path and not resource.is_directory for resource in members
                )
            ):
                raise ValidationError(
                    f"Codex interface {field} must identify an existing skill resource."
                )
        if field == "brand_color" and re.fullmatch(r"#[0-9A-Fa-f]{6}", text) is None:
            raise ValidationError("Codex brand_color must contain a six-digit hexadecimal color.")
    policy = payload.get("policy", {})
    if not is_json_dict(policy):
        raise ValidationError("Codex skill policy must be an object.")
    require_exact_json_fields(
        policy, allowed_fields={"allow_implicit_invocation", "products"}, label="Codex skill policy"
    )
    if "allow_implicit_invocation" in policy:
        require_bool(
            policy["allow_implicit_invocation"],
            label="Codex implicit invocation",
            build_error=ValidationError,
        )
    if "products" in policy:
        products = policy["products"]
        if (
            not is_str_list(products)
            or not products
            or not set(products).issubset({"CHAT", "CODEX"})
        ):
            raise ValidationError("Codex skill products must name CHAT or CODEX.")
    dependencies = payload.get("dependencies", {})
    if not is_json_dict(dependencies):
        raise ValidationError("Codex skill dependencies must be an object.")
    require_exact_json_fields(
        dependencies, allowed_fields={"tools"}, label="Codex skill dependencies"
    )
    tools = dependencies.get("tools", [])
    if not isinstance(tools, list):
        raise ValidationError("Codex tool dependencies must be an array.")
    for tool in tools:
        if not is_json_dict(tool):
            raise ValidationError("Codex tool dependency must be an object.")
        require_exact_json_fields(
            tool,
            allowed_fields={"type", "value", "description", "transport", "url"},
            label="Codex tool dependency",
        )
        if tool.get("type") != "mcp":
            raise ValidationError("Codex tool dependencies must use the supported mcp type.")
        for field, value in tool.items():
            require_bounded_trimmed_text(
                value,
                type_message=f"Codex dependency {field} must be text.",
                empty_message=f"Codex dependency {field} must not be blank.",
                max_length=MAX_MANIFEST_BYTES,
                max_length_message=f"Codex dependency {field} exceeds its text limit.",
            )
        if not isinstance(tool.get("value"), str) or not tool["value"]:
            raise ValidationError("Codex tool dependency must identify its required MCP service.")
    return payload
