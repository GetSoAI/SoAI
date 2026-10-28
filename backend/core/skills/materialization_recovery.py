"""SoAI - Truthful reconciliation of skill publication and owned staging [backend/core/skills/materialization_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.deadlines import MonotonicDeadline
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError, ValidationError
from core.events.types_skills import MaterializeSkillCommand
from core.files.locking import async_guarded_file_lock
from core.skills.materialization import SkillMaterializationReceipt, materialization_lock_path
from core.skills.materialization_authority import (
    require_live_materialization,
    require_materialization_workspace,
)
from core.skills.materialization_execution_dependencies import (
    SkillMaterializationServiceDependencies,
)
from core.skills.materialization_files import (
    publish_skill_staging,
    read_skill_directory_identity,
    remove_skill_staging,
    verify_skill_materialization,
)
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.timing.epoch import epoch_ms

__all__ = (
    "complete_materialization",
    "reconcile_materialization",
    "fail_materialization",
)


async def complete_materialization(
    deps: SkillMaterializationServiceDependencies,
    command: MaterializeSkillCommand,
    receipt: SkillMaterializationReceipt,
    *,
    publish_staging: bool = False,
    deadline: MonotonicDeadline | None = None,
) -> None:
    if receipt.publication_identity is None:
        raise StateError("Materialization publication evidence is unavailable.")
    await require_materialization_workspace(deps, receipt)
    if publish_staging:
        await run_joined_thread_call(
            publish_skill_staging,
            receipt.request.workspace_root,
            receipt.request.workspace_identity,
            receipt.staging_name,
            receipt.publication_identity,
            receipt.final_name,
            receipt.resources,
            deadline,
            receipt.request.manifest_path,
            receipt.request.executable_paths,
            task_name="skills.materialize.publish",
            retain_resources_until_complete=True,
        )
    await run_joined_thread_call(
        verify_skill_materialization,
        *receipt.verification_arguments(),
        deadline,
        task_name="skills.materialize.verify",
        retain_resources_until_complete=True,
    )
    if receipt.execution_phase == "publishing":
        await deps.skills.checkpoint_materialization(
            receipt.request_id,
            command.context.user_id,
            command.mutation_claim.fencing_token,
            "publishing",
            "verified",
            receipt.publication_identity,
        )
    await finalize(
        deps.registry,
        receipt.request_id,
        TaskStatus.COMPLETED,
        result=receipt.completed_result(),
        mutation_fencing_token=command.mutation_claim.fencing_token,
    )


async def reconcile_materialization(
    deps: SkillMaterializationServiceDependencies,
    command: MaterializeSkillCommand,
    receipt: SkillMaterializationReceipt,
    token: CancellationTokenProtocol,
    *,
    deadline: MonotonicDeadline | None = None,
) -> None:
    async with async_guarded_file_lock(
        materialization_lock_path(deps.plugin_directory, receipt.request_id),
        timeout=30.0,
        preserve_lock_file=True,
    ):
        if not await deps.tasks.validate_mutation_claim(
            receipt.request_id, command.mutation_claim.fencing_token, now_ms=epoch_ms()
        ):
            command.recovery_requested = True
            return
        if receipt.execution_phase == "conflict":
            await _finish_materialization_conflict(deps, command, receipt)
            return
        if receipt.execution_phase in {"creating", "staging", "contained_failure"}:
            task = await deps.registry.get(receipt.request_id, force_refresh=True)
            if task is None:
                raise StateError("Materialization task is unavailable for cleanup.")
            await _contain_materialization_failure(
                deps, command, receipt, cancelled=task.cancellation_requested_at_ms is not None
            )
            return
        if receipt.execution_phase not in {"publishing", "verified"}:
            raise StateError("Materialization recovery phase is invalid.")
        try:
            final_identity = await run_joined_thread_call(
                read_skill_directory_identity,
                receipt.request.workspace_root,
                receipt.request.workspace_identity,
                receipt.final_name,
                task_name="skills.materialize.observe",
                retain_resources_until_complete=True,
            )
            if final_identity is not None:
                await complete_materialization(deps, command, receipt, deadline=deadline)
                return
            if receipt.execution_phase == "verified":
                raise StateError("Previously verified materialized output is missing.")
            staging_identity = await run_joined_thread_call(
                read_skill_directory_identity,
                receipt.request.workspace_root,
                receipt.request.workspace_identity,
                receipt.staging_name,
                task_name="skills.materialize.observe_stage",
                retain_resources_until_complete=True,
            )
            if staging_identity is None or staging_identity != receipt.publication_identity:
                raise StateError(
                    "Materialization publication and owned staging are missing or changed."
                )
        except (StateError, ValidationError, FileNotFoundError):
            await deps.skills.checkpoint_materialization(
                receipt.request_id,
                command.context.user_id,
                command.mutation_claim.fencing_token,
                receipt.execution_phase or "",
                "conflict",
                None,
            )
            await _finish_materialization_conflict(deps, command, receipt)
            return
        try:
            token.raise_if_cancelled()
            await require_live_materialization(deps, command, receipt)
        except (TaskCancelledError, ValidationError):
            await _contain_materialization_failure(deps, command, receipt, cancelled=True)
            return
        await complete_materialization(
            deps, command, receipt, publish_staging=True, deadline=deadline
        )


async def _contain_materialization_failure(
    deps: SkillMaterializationServiceDependencies,
    command: MaterializeSkillCommand,
    receipt: SkillMaterializationReceipt,
    *,
    cancelled: bool,
) -> None:
    if receipt.execution_phase != "contained_failure":
        if receipt.staging_identity is not None:
            await run_joined_thread_call(
                remove_skill_staging,
                receipt.request.workspace_root,
                receipt.request.workspace_identity,
                receipt.staging_name,
                receipt.staging_identity,
                receipt.resources,
                None,
                receipt.request.manifest_path,
                task_name="skills.materialize.cleanup",
                retain_resources_until_complete=True,
            )
        await deps.skills.checkpoint_materialization(
            receipt.request_id,
            command.context.user_id,
            command.mutation_claim.fencing_token,
            receipt.execution_phase or "",
            "contained_failure",
            None,
            cancelled=cancelled,
        )
        receipt = await deps.skills.materialization(command.context.user_id, receipt.request_id)
    await finalize(
        deps.registry,
        receipt.request_id,
        TaskStatus.CANCELLED if receipt.failure_cancelled else TaskStatus.FAILED,
        result={
            "skill_id": receipt.request.skill_id,
            "materialized": False,
            "staging_cleanup_required": receipt.staging_cleanup_required,
        },
        error_message=(
            "Skill copying was cancelled."
            if receipt.failure_cancelled
            else "Skill files could not be materialized. Inspect the task result before retrying."
        ),
        mutation_fencing_token=command.mutation_claim.fencing_token,
    )


async def _finish_materialization_conflict(
    deps: SkillMaterializationServiceDependencies,
    command: MaterializeSkillCommand,
    receipt: SkillMaterializationReceipt,
) -> None:
    await finalize(
        deps.registry,
        receipt.request_id,
        TaskStatus.FAILED,
        result={
            "skill_id": receipt.request.skill_id,
            "publication_status": "conflict",
            "materialized": None,
        },
        error_message="Skill output or its workspace changed. No files were overwritten or recreated.",
        mutation_fencing_token=command.mutation_claim.fencing_token,
    )


async def fail_materialization(
    deps: SkillMaterializationServiceDependencies,
    command: MaterializeSkillCommand,
    *,
    cancelled: bool,
    created_staging_identity: tuple[int, int] | None = None,
) -> None:
    command.recovery_requested = True
    async with async_guarded_file_lock(
        materialization_lock_path(
            deps.plugin_directory, command.mutation_claim.request_id, writer=True
        ),
        timeout=30.0,
        preserve_lock_file=True,
    ):
        async with async_guarded_file_lock(
            materialization_lock_path(deps.plugin_directory, command.mutation_claim.request_id),
            timeout=30.0,
            preserve_lock_file=True,
        ):
            if not await deps.tasks.validate_mutation_claim(
                command.mutation_claim.request_id,
                command.mutation_claim.fencing_token,
                now_ms=epoch_ms(),
            ):
                return
            receipt = await deps.skills.materialization(
                command.context.user_id, command.mutation_claim.request_id
            )
            if receipt.terminal_status is not None or receipt.execution_phase in {
                "publishing",
                "verified",
            }:
                return
            if receipt.execution_phase == "creating" and created_staging_identity is not None:
                await deps.skills.checkpoint_materialization(
                    receipt.request_id,
                    command.context.user_id,
                    command.mutation_claim.fencing_token,
                    "creating",
                    "staging",
                    created_staging_identity,
                )
                receipt = await deps.skills.materialization(
                    command.context.user_id, receipt.request_id
                )
            if receipt.execution_phase == "conflict":
                await _finish_materialization_conflict(deps, command, receipt)
            else:
                await _contain_materialization_failure(deps, command, receipt, cancelled=cancelled)
            command.recovery_requested = False
