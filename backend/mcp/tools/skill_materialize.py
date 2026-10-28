"""SoAI - Internal admitted skill materialization and durable receipt replay [backend/mcp/tools/skill_materialize.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.database.mutation_requests import MutationAdmissionDraft
from core.errors.exceptions import SoAITimeoutError, StateError
from core.events.types_tasks import MutationDispatchRequestedEvent
from core.files.anchored_directory import open_anchored_workspace
from core.mutations.identifiers import create_mutation_request_id
from core.serialization.json import serialize_json_compact_stable
from core.skills.materialization import SkillMaterializationReceipt, SkillMaterializationRequest
from core.skills.materialization_files import verify_skill_materialization
from core.skills.publication_layout import skill_profile_publication
from core.skills.selection import require_skill_id
from core.state.access import AccessAction
from core.tasks.creation import create
from core.tasks.type_catalog import TASK_TYPE_MCP_TOOL_CALL
from mcp.tools.access_control import require_tool_action
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError, build_invalid_params_error
from mcp.tools.files_access import get_workspace_context
from mcp.tools.skill_context import require_skill_tool_context

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol


__all__ = ("tool_skill_materialize",)


async def tool_skill_materialize(
    utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict
) -> JSONDict:
    reject_unexpected_parameters(arguments, {"skill_id"})
    authority = require_skill_tool_context(utility_tools, tool_name="skill_materialize")
    if authority.request.agent_mode != "execute":
        raise build_invalid_params_error("Skill materialization requires execute mode.")
    user_id = await require_tool_action(
        utility_tools, action=AccessAction.MCP_USE, tool_name="skill_materialize"
    )
    if user_id != authority.identity.user_id:
        raise MCPToolError(-32603, "Skill materialization ownership is inconsistent.")
    skill_id = require_skill_id(arguments.get("skill_id"))
    if skill_id not in authority.execution.active_skill_ids:
        raise build_invalid_params_error("Activate this skill before materializing its files.")
    selected = next(
        (skill for skill in authority.execution.snapshot.available if skill.skill_id == skill_id),
        None,
    )
    if selected is None:
        raise build_invalid_params_error("Skill is unavailable in this execution.")
    await utility_tools.database_skills.execution_resource(authority.identity, skill_id, "SKILL.md")
    _, _, workspace_root = get_workspace_context(utility_tools)
    workspace_identity = await run_joined_thread_call(
        _workspace_identity,
        workspace_root,
        task_name="skills.materialize.admit_workspace",
        retain_resources_until_complete=True,
    )
    request = SkillMaterializationRequest(
        authority.identity,
        authority.execution.snapshot.root_input_id,
        skill_id,
        selected.package_digest,
        workspace_root,
        workspace_identity,
        skill_profile_publication(selected.profile),
        selected.profile.digest if selected.profile else None,
    )
    receipt = await utility_tools.database_skills.materialization_receipt(
        user_id, request.operation_key
    )
    if receipt is not None and (
        receipt.request.workspace_root != workspace_root
        or receipt.request.workspace_identity != workspace_identity
    ):
        return {
            "skill_id": skill_id,
            "skill_name": selected.manifest.name,
            "task_id": receipt.request_id,
            "status": "conflict",
            "materialized": None,
        }
    if receipt is None:
        request_id = create_mutation_request_id()
        task = await create(
            utility_tools.task_registry,
            TASK_TYPE_MCP_TOOL_CALL,
            user_id,
            str(user_id),
            "conversation",
            task_id=request_id,
            cancellation_id=authority.request.cancellation_id,
            metadata={
                "tool_name": "skill_materialize",
                "conv_id": authority.identity.conv_id,
                "skill_id": skill_id,
            },
            mutation_admission=MutationAdmissionDraft(
                request_id=request_id,
                conflict_keys=(f"skill_materialize:{request.operation_key}",),
                shared_conflict_keys=(),
                operation_type="skill_materialize",
                target_identity=request.operation_key,
                authorization_scope="mcp_use",
                command_payload=serialize_json_compact_stable(request.payload()),
                schema_discriminator="skill_materialize_v1",
            ),
        )
        receipt = await utility_tools.database_skills.materialization(user_id, task.task_id)
    if receipt.terminal_status is None and not receipt.recovery_required:
        await utility_tools.event_bus.publish(MutationDispatchRequestedEvent())
        try:
            await utility_tools.task_registry.wait_for_completion(receipt.request_id, timeout=300.0)
        except SoAITimeoutError:
            receipt = await utility_tools.database_skills.materialization(
                user_id, receipt.request_id
            )
            return await _receipt_result(receipt, selected.manifest.name)
        receipt = await utility_tools.database_skills.materialization(user_id, receipt.request_id)
    return await _receipt_result(receipt, selected.manifest.name)


async def _receipt_result(receipt: SkillMaterializationReceipt, skill_name: str) -> JSONDict:
    if receipt.recovery_required:
        return {
            "skill_id": receipt.request.skill_id,
            "skill_name": skill_name,
            "task_id": receipt.request_id,
            "status": "recovery_required",
            "materialized": None,
        }
    if receipt.terminal_status is None:
        return {
            "skill_id": receipt.request.skill_id,
            "skill_name": skill_name,
            "task_id": receipt.request_id,
            "status": "pending",
            "materialized": None,
        }
    if receipt.terminal_status != "completed":
        return {
            "skill_id": receipt.request.skill_id,
            "skill_name": skill_name,
            "task_id": receipt.request_id,
            "status": receipt.terminal_status,
            "materialized": None,
            "details": receipt.terminal_result,
        }
    if receipt.terminal_result is None:
        raise StateError("Completed materialization has no durable verification evidence.")
    verification_arguments = receipt.verification_arguments()
    try:
        await run_joined_thread_call(
            verify_skill_materialization,
            *verification_arguments,
            task_name="skills.materialize.replay_verify",
            retain_resources_until_complete=True,
        )
    except (StateError, FileNotFoundError):
        return {
            "skill_id": receipt.request.skill_id,
            "skill_name": skill_name,
            "task_id": receipt.request_id,
            "status": "conflict",
            "materialized": None,
        }
    return {
        **receipt.terminal_result,
        "skill_name": skill_name,
        "task_id": receipt.request_id,
        "status": "completed",
    }


def _workspace_identity(path: str) -> tuple[int, int]:
    with open_anchored_workspace(path) as workspace:
        return workspace.identity
