"""SoAI - Internal admitted skill activation and bounded resource reads [backend/mcp/tools/skill_read.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.mcp.argument_numbers import parse_required_json_int_value
from core.skills.limits import MAX_INVOCATION_ARGUMENT_CHARACTERS, MAX_PATH_BYTES
from core.skills.publication_layout import skill_profile_publication
from core.skills.selection import require_skill_id
from core.skills.serialization import skill_resources_payload
from core.validation.record_fields import require_bool
from core.validation.strings import require_bounded_trimmed_text
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import build_invalid_params_error
from mcp.tools.file_text_response_budget import build_prompt_safe_line_payload
from mcp.tools.skill_context import require_skill_tool_context

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_skill_read",)


async def tool_skill_read(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(
        arguments, {"skill_id", "path", "offset", "limit", "arguments", "source_relative"}
    )
    authority = require_skill_tool_context(utility_tools, tool_name="skill_read")
    skill_id = require_skill_id(arguments.get("skill_id"))
    if "path" not in arguments:
        if "offset" in arguments or "limit" in arguments or "source_relative" in arguments:
            raise build_invalid_params_error("Paging requires a resource path.")
        callback = authority.request.skill_activation_callback
        if callback is None:
            raise build_invalid_params_error("Skill activation requires an active tool phase.")
        selected_skill = next(
            (
                skill
                for skill in authority.execution.snapshot.available
                if skill.skill_id == skill_id
            ),
            None,
        )
        if selected_skill is None:
            raise build_invalid_params_error("Skill is not available in this execution.")
        result: JSONDict = {
            "skill_id": skill_id,
            "skill_name": selected_skill.manifest.name,
            "activated": True,
            "resources": skill_resources_payload(selected_skill.resources),
        }
        if "arguments" in arguments:
            activation_arguments = require_bounded_trimmed_text(
                arguments["arguments"],
                type_message="Skill arguments must be a string.",
                empty_message="Skill arguments must be text.",
                max_length=MAX_INVOCATION_ARGUMENT_CHARACTERS,
                max_length_message="Skill arguments exceed the invocation text limit.",
                nul_message="Skill arguments must not contain NUL characters.",
                preserve_whitespace=True,
                allow_blank=True,
            )
            authority.request.skill_execution_context = await callback(
                skill_id, authority.call.call_id, result, activation_arguments
            )
        else:
            authority.request.skill_execution_context = await callback(
                skill_id, authority.call.call_id, result
            )
        return result
    if "arguments" in arguments:
        raise build_invalid_params_error(
            "Invocation arguments cannot be supplied on a resource read."
        )
    path = arguments["path"]
    if not isinstance(path, str) or not path:
        raise build_invalid_params_error(
            "Skill resource path must be an exact package-relative name."
        )
    try:
        path_bytes = path.encode("utf-8")
    except UnicodeEncodeError as exception:
        raise build_invalid_params_error(
            "Skill resource path contains invalid Unicode."
        ) from exception
    if len(path_bytes) > MAX_PATH_BYTES:
        raise build_invalid_params_error("Skill resource path exceeds the package path limit.")
    if skill_id not in authority.execution.active_skill_ids:
        raise build_invalid_params_error("Activate this skill before reading its resources.")
    offset = parse_required_json_int_value(
        arguments.get("offset", 1),
        build_error=build_invalid_params_error,
        integer_message="offset must be an integer",
        range_message="offset must be positive",
        min_value=1,
        max_value=2_147_483_647,
    )
    limit = parse_required_json_int_value(
        arguments.get("limit", 200),
        build_error=build_invalid_params_error,
        integer_message="limit must be an integer",
        range_message="limit must be between 1 and 2000",
        min_value=1,
        max_value=2000,
    )
    source_relative = require_bool(
        arguments.get("source_relative", False),
        label="Skill source-relative read",
        build_error=build_invalid_params_error,
    )
    active_skill = next(
        skill for skill in authority.execution.snapshot.available if skill.skill_id == skill_id
    )
    if source_relative:
        layout = skill_profile_publication(active_skill.profile)
        expected_digest = dict(layout.supporting_digests).get(path) if layout else None
        if expected_digest is None:
            raise build_invalid_params_error(
                "This source path is not a captured supporting resource of the skill."
            )
        member = await utility_tools.database_skills.execution_resource(
            authority.identity, skill_id, path, supporting=True
        )
        if member.digest != expected_digest:
            raise StateError("Supporting resource differs from its admitted source binding.")
    else:
        member = await utility_tools.database_skills.execution_resource(
            authority.identity, skill_id, path
        )
    metadata: JSONDict = {
        "skill_id": skill_id,
        "skill_name": active_skill.manifest.name,
        "digest": member.digest,
        "size_bytes": len(member.content),
        "is_directory": member.is_directory,
    }
    if source_relative:
        metadata["source_relative"] = True
    selected_tools = authority.request.mcp_tool_context
    if (
        authority.request.agent_mode == "execute"
        and selected_tools is not None
        and "skill_materialize" in selected_tools.tool_map
    ):
        metadata["materialize_hint"] = (
            "Use skill_materialize to copy the active skill's complete files into the workspace."
        )
    try:
        content = member.content.decode("utf-8")
    except UnicodeDecodeError:
        return {**metadata, "path": path, "binary": True, "content_omitted": True}
    if "\x00" in content or member.is_directory:
        return {
            **metadata,
            "path": path,
            "binary": not member.is_directory,
            "content_omitted": True,
        }
    lines = content.splitlines()
    selected = lines[offset - 1 : offset - 1 + limit]
    return build_prompt_safe_line_payload(
        path=path,
        mode="slice",
        offset=offset,
        limit=limit,
        total_lines=len(lines),
        selected=selected,
        start_line=offset if selected else None,
        render="raw",
        line_limit_truncated=offset - 1 + len(selected) < len(lines),
        indentation=None,
        additional_fields={**metadata, "binary": False},
    )
