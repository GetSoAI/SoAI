"""SoAI - Live skill materialization claims and workspace authority [backend/core/skills/materialization_authority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.conversations.conversation_model_settings_resolution import (
    require_conversation_model_settings,
)
from core.errors.exceptions import StateError, ValidationError
from core.events.types_skills import MaterializeSkillCommand
from core.skills.materialization import SkillMaterializationReceipt
from core.skills.materialization_execution_dependencies import (
    SkillMaterializationServiceDependencies,
)
from core.skills.materialization_files import read_skill_directory_identity
from core.timing.epoch import epoch_ms
from core.workspaces.conversation_workspace_path import (
    read_conversation_workspace_path_override,
    resolve_effective_conversation_workspace_path,
)
from core.workspaces.user_workspace_path import require_user_record_workspace_path

__all__ = ("require_materialization_workspace", "require_live_materialization")


async def require_materialization_workspace(
    deps: SkillMaterializationServiceDependencies, receipt: SkillMaterializationReceipt
) -> None:
    identity = receipt.request.identity
    user = await deps.users.get_account_by_id(identity.user_id)
    conversation = await deps.conversations.get_conversation(identity.conv_id, identity.user_id)
    if user is None or conversation is None:
        raise ValidationError("Materialization conversation or owner is unavailable.")
    settings = require_conversation_model_settings(
        conversation.get("model_settings"), exception_type=ValidationError
    )
    current_root = resolve_effective_conversation_workspace_path(
        files=deps.files,
        user_workspace_path=require_user_record_workspace_path(user),
        override_workspace_path=read_conversation_workspace_path_override(settings),
        require_existing_directories=True,
    )
    if current_root != receipt.request.workspace_root:
        raise ValidationError("Materialization workspace configuration changed.")
    await run_joined_thread_call(
        read_skill_directory_identity,
        current_root,
        receipt.request.workspace_identity,
        None,
        task_name="skills.materialize.workspace",
        retain_resources_until_complete=True,
    )


async def require_live_materialization(
    deps: SkillMaterializationServiceDependencies,
    command: MaterializeSkillCommand,
    receipt: SkillMaterializationReceipt,
) -> None:
    if not await deps.tasks.validate_mutation_claim(
        receipt.request_id, command.mutation_claim.fencing_token, now_ms=epoch_ms()
    ):
        raise StateError("Materialization claim is no longer live.")
    task = await deps.registry.get(receipt.request_id, force_refresh=True)
    if task is None or task.status.is_terminal() or task.cancellation_requested_at_ms is not None:
        raise TaskCancelledError(command.context.cancellation_id)
    await require_materialization_workspace(deps, receipt)
    await deps.skills.execution_resource(
        receipt.request.identity, receipt.request.skill_id, "SKILL.md"
    )
