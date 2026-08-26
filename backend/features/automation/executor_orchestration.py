"""SoAI - Automation executor orchestration [backend/features/automation/executor_orchestration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.automation.automation_constants import (
    AUTOMATION_RESULT_EXCERPT_CHARS,
)
from core.automation.automation_interactive_tool_approval import (
    extract_interactive_tool_approval,
)
from core.automation.automation_run_task_lifecycle import (
    mark_automation_run_task_working,
)
from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from features.agent.runtime.execution_preparation import (
    build_agent_turn_engine_dependencies,
)
from features.agent.session.runtime_resolution import (
    resolve_required_agent_runtime_settings,
)
from features.automation.events import publish_automation_conversation_created
from features.automation.execution_deadline import enforce_automation_run_deadline
from features.automation.execution_failure_handling import (
    handle_automation_run_failure,
)
from features.automation.execution_messages import create_automation_conversation
from features.automation.execution_owner_task_progress import (
    update_run_owner_task_progress_noncritical,
)
from features.automation.execution_settings import build_automation_request_context
from features.automation.execution_snapshot import (
    resolve_automation_run_execution_snapshot,
)
from features.automation.execution_turns import execute_automation_turn
from features.automation.run_terminal_transitions import (
    complete_automation_run_terminal,
    finalize_automation_run_task_terminal,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("execute_automation_run_orchestration",)

OPERATION = "automation.executor.execute"


async def _ensure_run_not_cancelled(
    api_dependencies: ApiDependencies,
    *,
    cancellation_id: str,
) -> None:
    if await api_dependencies.cancellation_history.is_cancelled(cancellation_id):
        raise TaskCancelledError(cancellation_id, "Automation run was cancelled.")


async def execute_automation_run_orchestration(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    run_id: str,
    run_record: JSONDict,
    owner_task_id: str | None,
) -> None:
    timeout_task: asyncio.Task[None] | None = None
    automation_id = str(run_record.get("automation_id") or "").strip()
    user_id: int | None = None
    latest_excerpt: str | None = None
    run_completed_recorded = False
    try:
        snapshot = await resolve_automation_run_execution_snapshot(
            api_dependencies,
            run_record=run_record,
        )
        automation_id = snapshot.automation_id
        user_id = snapshot.user_id
        title = snapshot.title
        max_run_minutes = snapshot.max_run_minutes
        normalized_turns = snapshot.normalized_turns
        conversation_model_settings = snapshot.conversation_model_settings
        requested_model = snapshot.requested_model
        resolution = await resolve_required_agent_runtime_settings(
            api_dependencies=api_dependencies,
            user_id=user_id,
            model_settings=conversation_model_settings,
            request_model=None,
            require_context_window=True,
        )
        agent_settings = resolution.settings
        request_context = build_automation_request_context(
            user_id=user_id,
            run_id=run_id,
            requested_model=requested_model,
            agent_settings=agent_settings,
            interactive_tool_approval=extract_interactive_tool_approval(
                conversation_model_settings,
            ),
        )
        timeout_task = create_ephemeral_task(
            enforce_automation_run_deadline(
                api_dependencies,
                request_context=request_context,
                max_run_minutes=max_run_minutes,
            ),
            name=f"automation-run-timeout:{run_id}",
        )
        total_turns = len(normalized_turns)
        await update_run_owner_task_progress_noncritical(
            api_dependencies,
            logger,
            owner_task_id=owner_task_id,
            progress_current=0,
            progress_total=total_turns,
            status_message="Running automation run.",
            operation=f"{OPERATION}.progress.initialize",
            run_id=run_id,
            automation_id=automation_id,
        )
        await mark_automation_run_task_working(
            api_dependencies.task_registry,
            owner_task_id=owner_task_id,
        )
        await _ensure_run_not_cancelled(
            api_dependencies,
            cancellation_id=request_context.cancellation_id,
        )
        session = await create_automation_conversation(
            api_dependencies,
            user_id=user_id,
            title=title,
            model_settings=snapshot.effective_conversation_model_settings,
        )
        attached = await api_dependencies.database_automation_runs.attach_conversation(
            run_id,
            user_id,
            session.conv_id,
            now_ms=epoch_ms(),
        )
        if attached is None:
            deleted_record = await api_dependencies.database_conversations.delete_conversation(
                session.conv_id,
                user_id,
            )
            if deleted_record is None:
                raise StateError(
                    "Automation run conversation could not be attached and rollback failed.",
                )
            raise StateError("Automation run conversation could not be attached.")
        await publish_automation_conversation_created(
            api_dependencies.event_bus,
            user_id=user_id,
            conversation_record=session.conversation_record,
        )
        deps = build_agent_turn_engine_dependencies(
            api_dependencies=api_dependencies,
            logger=logger,
        )
        for turn_index, turn_text in enumerate(normalized_turns):
            await _ensure_run_not_cancelled(
                api_dependencies,
                cancellation_id=request_context.cancellation_id,
            )
            await update_run_owner_task_progress_noncritical(
                api_dependencies,
                logger,
                owner_task_id=owner_task_id,
                progress_current=turn_index,
                progress_total=total_turns,
                status_message=f"Running turn {turn_index + 1}/{total_turns}.",
                operation=f"{OPERATION}.progress.before_turn",
                run_id=run_id,
                automation_id=automation_id,
            )
            assistant_text = await execute_automation_turn(
                api_dependencies,
                automation_id=automation_id,
                run_id=run_id,
                turn_index=turn_index,
                turn_text=turn_text,
                conversation_model_settings=conversation_model_settings,
                session=session,
                request_context=request_context,
                requested_model=requested_model,
                agent_settings=agent_settings,
                deps=deps,
            )
            latest_excerpt = assistant_text[:AUTOMATION_RESULT_EXCERPT_CHARS] or latest_excerpt
            await update_run_owner_task_progress_noncritical(
                api_dependencies,
                logger,
                owner_task_id=owner_task_id,
                progress_current=turn_index + 1,
                progress_total=total_turns,
                status_message=f"Completed turn {turn_index + 1}/{total_turns}.",
                operation=f"{OPERATION}.progress.after_turn",
                run_id=run_id,
                automation_id=automation_id,
            )
        completed_run = await complete_automation_run_terminal(
            api_dependencies,
            run_id=run_id,
            user_id=user_id,
            final_status="completed",
            result_excerpt=latest_excerpt,
        )
        if completed_run is None:
            raise StateError("Automation run completion could not be recorded.")
        run_completed_recorded = True
        try:
            await finalize_automation_run_task_terminal(
                api_dependencies,
                owner_task_id=owner_task_id,
                final_status="completed",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Automation run task completion finalization failed after completion persistence.",
                operation=OPERATION,
                level="error",
                details={"run_id": run_id, "automation_id": automation_id},
            )
    except SoAIError as exception:
        await handle_automation_run_failure(
            api_dependencies,
            logger=logger,
            operation=OPERATION,
            run_id=run_id,
            automation_id=automation_id,
            user_id=user_id,
            owner_task_id=owner_task_id,
            latest_excerpt=latest_excerpt,
            exception=exception,
            run_completed_recorded=run_completed_recorded,
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Automation run orchestration failed.",
            operation=OPERATION,
            details={"run_id": run_id, "automation_id": automation_id},
        )
        await handle_automation_run_failure(
            api_dependencies,
            logger=logger,
            operation=OPERATION,
            run_id=run_id,
            automation_id=automation_id,
            user_id=user_id,
            owner_task_id=owner_task_id,
            latest_excerpt=latest_excerpt,
            exception=exception,
            run_completed_recorded=run_completed_recorded,
        )
    finally:
        if timeout_task is not None:
            await cancel_and_await((timeout_task,), logger=logger, task_label="automation timeout")
