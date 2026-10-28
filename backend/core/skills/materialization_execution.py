"""SoAI - Fenced durable skill copying and publication [backend/core/skills/materialization_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_skills import MaterializeSkillCommand
from core.files.locking import async_guarded_file_lock
from core.logging.trace import get_logger
from core.skills.materialization import materialization_lock_path
from core.skills.materialization_authority import require_live_materialization
from core.skills.materialization_execution_dependencies import (
    SkillMaterializationServiceDependencies,
)
from core.skills.materialization_files import (
    create_skill_staging,
    populate_skill_staging,
)
from core.skills.materialization_recovery import (
    complete_materialization,
    fail_materialization,
    reconcile_materialization,
)
from core.system.native_image_budget import native_image_allowance
from core.tasks.cancellation_token_scope import cancellation_token_scope

__all__ = ("SkillMaterializationService",)


LOGGER_NAME = "SoAI.core.skills.materialization_execution"
OPERATION_MATERIALIZE = "skills.materialize"
EXECUTION_TIMEOUT_SECONDS = 300.0


class SkillMaterializationService:
    def __init__(self, deps: SkillMaterializationServiceDependencies) -> None:
        self._deps = deps

    async def handle(self, event: Event) -> None:
        if not isinstance(event, MaterializeSkillCommand):
            return
        command = event
        created_staging: list[tuple[int, int]] = []
        deadline = deadline_after(EXECUTION_TIMEOUT_SECONDS)
        try:
            async with asyncio.timeout_at(deadline.deadline_monotonic) as timeout:
                async with async_guarded_file_lock(
                    materialization_lock_path(
                        self._deps.plugin_directory, command.mutation_claim.request_id, writer=True
                    ),
                    timeout=30.0,
                    preserve_lock_file=True,
                ):
                    async with cancellation_token_scope(
                        self._deps.token_collection,
                        self._deps.cancellation_history,
                        self._deps.cancellation_event_bus,
                        cancellation_id=command.context.cancellation_id,
                        owner="skill_materialize",
                    ) as token:

                        def cancel_copy() -> None:
                            token.cancel("Skill copying cancelled.")

                        receipt = await self._deps.skills.materialization(
                            command.context.user_id, command.mutation_claim.request_id
                        )
                        if receipt.terminal_status is not None:
                            return
                        allowance = native_image_allowance(
                            EXECUTION_TIMEOUT_SECONDS,
                            roots=(),
                            planned_paths=(
                                resource.path
                                for resource in receipt.resources
                                if not resource.is_directory
                            ),
                        )
                        deadline = MonotonicDeadline(
                            deadline.deadline_monotonic
                            + allowance.seconds
                            - EXECUTION_TIMEOUT_SECONDS
                        )
                        timeout.reschedule(deadline.deadline_monotonic)
                        if receipt.execution_phase != "accepted":
                            await reconcile_materialization(
                                self._deps, command, receipt, token, deadline=deadline
                            )
                            return
                        token.raise_if_cancelled()
                        await require_live_materialization(self._deps, command, receipt)
                        members = await self._deps.skills.materialization_members(receipt.request)
                        with self._deps.storage.reserve_disk_space(
                            path=receipt.request.workspace_root,
                            required_bytes=sum(
                                resource.size_bytes for resource in receipt.resources
                            )
                            + 4096 * (len(receipt.resources) + 1),
                            operation=OPERATION_MATERIALIZE,
                        ):
                            await self._deps.skills.checkpoint_materialization(
                                receipt.request_id,
                                command.context.user_id,
                                command.mutation_claim.fencing_token,
                                "accepted",
                                "creating",
                                None,
                            )
                            staging_identity = await run_joined_thread_call(
                                create_skill_staging,
                                receipt.request.workspace_root,
                                receipt.request.workspace_identity,
                                receipt.staging_name,
                                deadline,
                                token,
                                task_name="skills.materialize.create",
                                retain_resources_until_complete=True,
                                cancelled_result_cleanup=created_staging.append,
                            )
                            created_staging.append(staging_identity)
                            await self._deps.skills.checkpoint_materialization(
                                receipt.request_id,
                                command.context.user_id,
                                command.mutation_claim.fencing_token,
                                "creating",
                                "staging",
                                staging_identity,
                            )
                            await run_joined_thread_call(
                                populate_skill_staging,
                                receipt.request.workspace_root,
                                receipt.request.workspace_identity,
                                receipt.staging_name,
                                staging_identity,
                                members,
                                receipt.request.publication_digest,
                                token,
                                deadline,
                                receipt.request.manifest_path,
                                receipt.request.executable_paths,
                                task_name="skills.materialize.copy",
                                retain_resources_until_complete=True,
                                on_cancel=cancel_copy,
                            )
                            async with async_guarded_file_lock(
                                materialization_lock_path(
                                    self._deps.plugin_directory, receipt.request_id
                                ),
                                timeout=30.0,
                                preserve_lock_file=True,
                            ):
                                token.raise_if_cancelled()
                                await require_live_materialization(self._deps, command, receipt)
                                await self._deps.skills.checkpoint_materialization(
                                    receipt.request_id,
                                    command.context.user_id,
                                    command.mutation_claim.fencing_token,
                                    "staging",
                                    "publishing",
                                    staging_identity,
                                )
                                receipt = await self._deps.skills.materialization(
                                    command.context.user_id, receipt.request_id
                                )
                                await complete_materialization(
                                    self._deps,
                                    command,
                                    receipt,
                                    publish_staging=True,
                                    deadline=deadline,
                                )
        except (asyncio.CancelledError, TaskCancelledError):
            await uncancel_then_cleanup(
                fail_materialization(
                    self._deps,
                    command,
                    cancelled=True,
                    created_staging_identity=created_staging[0] if created_staging else None,
                )
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Skill materialization could not finish its current attempt.",
                operation=OPERATION_MATERIALIZE,
                details={"task_id": command.mutation_claim.request_id},
            )
            await fail_materialization(
                self._deps,
                command,
                cancelled=False,
                created_staging_identity=created_staging[0] if created_staging else None,
            )
