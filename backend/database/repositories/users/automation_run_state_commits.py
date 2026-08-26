"""SoAI - Automation run terminal state commits and notifications [backend/database/repositories/users/automation_run_state_commits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.notifications.notification_contracts import NotificationType
from core.users.user_id import is_strict_user_id
from core.validation.booleans import parse_bool
from database.repositories.users.automation_run_completion_notification_delivery import (
    emit_automation_run_completion_notification_if_enabled,
)
from database.repositories.users.automation_run_terminal_transitions import (
    sync_complete_run_terminal,
)
from database.repositories.users.automation_run_transitions import (
    sync_mark_restarted_running_runs,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from typing import Literal

    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

    type AutomationRunTerminalStatus = Literal["completed", "cancelled", "abandoned", "error"]

__all__ = (
    "complete_automation_run_abandoned",
    "complete_automation_run_cancelled",
    "complete_automation_run_completed",
    "complete_automation_run_error",
    "mark_restarted_running_automation_runs",
)


def _read_automation_run_notification_emission_settings(
    config: ConfigProtocol,
) -> bool:
    emit_notifications = parse_bool(
        config.get("SERVER.WEBUI.NOTIFICATIONS.EMIT_ON_AUTOMATION_COMPLETE", False),
        default=False,
    )
    return bool(emit_notifications)


async def _emit_completion_notifications_for_records(
    database_notifications: DatabaseNotificationsProtocol,
    run_records: Sequence[JSONDict],
    *,
    emit_notifications: bool,
    fallback_run_id: str,
    fallback_user_id: int,
    notification_type: NotificationType,
    status_message: str | None,
) -> None:
    if not emit_notifications:
        return
    for run_record in run_records:
        run_id_value = run_record.get("run_id")
        notification_run_id = run_id_value if isinstance(run_id_value, str) else fallback_run_id
        user_id_value = run_record.get("user_id")
        notification_user_id = (
            user_id_value if is_strict_user_id(user_id_value) else fallback_user_id
        )
        await emit_automation_run_completion_notification_if_enabled(
            database_notifications,
            run_record,
            emit_notifications=True,
            run_id=notification_run_id,
            user_id=notification_user_id,
            notification_type=notification_type,
            status_message=status_message,
        )


async def _complete_automation_run_terminal(
    deps: DatabaseRepositoryDependencies,
    database_notifications: DatabaseNotificationsProtocol,
    config: ConfigProtocol,
    *,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    final_status: AutomationRunTerminalStatus,
    status_message: str | None,
    result_excerpt: str | None,
    notification_type: NotificationType,
) -> JSONDict | None:
    emit_notifications = _read_automation_run_notification_emission_settings(config)
    result = await deps.core.writer.queue_write_operation(
        sync_complete_run_terminal,
        run_id,
        user_id,
        finished_at_ms,
        final_status,
        status_message,
        result_excerpt,
    )
    if isinstance(result, dict):
        notify_domain_event_outbox_dispatch_requested(deps.event_bus)
        await _emit_completion_notifications_for_records(
            database_notifications,
            (result,),
            emit_notifications=emit_notifications,
            fallback_run_id=run_id,
            fallback_user_id=user_id,
            notification_type=notification_type,
            status_message=status_message,
        )
    return result


async def complete_automation_run_completed(
    deps: DatabaseRepositoryDependencies,
    database_notifications: DatabaseNotificationsProtocol,
    config: ConfigProtocol,
    *,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    result_excerpt: str | None,
) -> JSONDict | None:
    return await _complete_automation_run_terminal(
        deps,
        database_notifications,
        config,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="completed",
        status_message=None,
        result_excerpt=result_excerpt,
        notification_type=NotificationType.SUCCESS,
    )


async def complete_automation_run_cancelled(
    deps: DatabaseRepositoryDependencies,
    database_notifications: DatabaseNotificationsProtocol,
    config: ConfigProtocol,
    *,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    status_message: str,
    result_excerpt: str | None,
) -> JSONDict | None:
    return await _complete_automation_run_terminal(
        deps,
        database_notifications,
        config,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="cancelled",
        status_message=status_message,
        result_excerpt=result_excerpt,
        notification_type=NotificationType.WARNING,
    )


async def complete_automation_run_error(
    deps: DatabaseRepositoryDependencies,
    database_notifications: DatabaseNotificationsProtocol,
    config: ConfigProtocol,
    *,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    status_message: str,
    result_excerpt: str | None,
) -> JSONDict | None:
    return await _complete_automation_run_terminal(
        deps,
        database_notifications,
        config,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="error",
        status_message=status_message,
        result_excerpt=result_excerpt,
        notification_type=NotificationType.ERROR,
    )


async def complete_automation_run_abandoned(
    deps: DatabaseRepositoryDependencies,
    database_notifications: DatabaseNotificationsProtocol,
    config: ConfigProtocol,
    *,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    status_message: str,
    result_excerpt: str | None,
) -> JSONDict | None:
    return await _complete_automation_run_terminal(
        deps,
        database_notifications,
        config,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="abandoned",
        status_message=status_message,
        result_excerpt=result_excerpt,
        notification_type=NotificationType.WARNING,
    )


async def mark_restarted_running_automation_runs(
    deps: DatabaseRepositoryDependencies,
    database_notifications: DatabaseNotificationsProtocol,
    config: ConfigProtocol,
    *,
    now_ms: int,
    status_message: str,
) -> list[JSONDict]:
    emit_notifications = _read_automation_run_notification_emission_settings(config)
    result = await deps.core.writer.queue_write_operation(
        sync_mark_restarted_running_runs,
        now_ms,
        status_message,
    )
    if result:
        notify_domain_event_outbox_dispatch_requested(deps.event_bus)
    await _emit_completion_notifications_for_records(
        database_notifications,
        result,
        emit_notifications=emit_notifications,
        fallback_run_id="",
        fallback_user_id=0,
        notification_type=NotificationType.ERROR,
        status_message=status_message,
    )
    return result
