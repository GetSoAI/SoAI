"""SoAI - Automation definition update lifecycle [backend/core/automation/automation_definition_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_conversation_model_settings import (
    resolve_automation_conversation_model_settings,
)
from core.automation.automation_mutation_results import AutomationUpdateResult
from core.automation.automation_run_task_lifecycle import (
    finalize_abandoned_automation_owner_task_ids,
    require_automation_identifier_list,
)
from core.events.conversation_publication import publish_conversation_updated
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.automation.protocols_database import DatabaseAutomationsProtocol
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = ("update_automation_definition",)


async def _propagate_updated_automation_settings(
    database_automations: DatabaseAutomationsProtocol,
    *,
    automation_id: str,
    user_id: int,
    previous: JSONDict | None,
    updated: JSONDict,
    event_bus: EventBusProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> AutomationUpdateResult:
    model_settings = updated.get("model_settings")
    if not isinstance(model_settings, dict):
        return AutomationUpdateResult(automation=updated)
    if previous is not None and previous.get("model_settings") == model_settings:
        return AutomationUpdateResult(automation=updated)
    conversation_model_settings = await resolve_automation_conversation_model_settings(
        user_id=user_id,
        model_settings=model_settings,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
    )
    versions = await database_automations.propagate_automation_conversation_model_settings(
        automation_id,
        user_id,
        conversation_model_settings,
    )
    for version in versions:
        await publish_conversation_updated(
            event_bus,
            user_id=user_id,
            conv_id=version.conv_id,
            last_modified_at_ms=version.last_modified_at_ms,
            settings_authority_changed=True,
        )
    return AutomationUpdateResult(automation=updated, conversation_versions=versions)


async def update_automation_definition(
    database_automations: DatabaseAutomationsProtocol,
    task_registry: TaskRegistryProtocol,
    *,
    automation_id: str,
    user_id: int,
    payload: JSONDict,
    event_bus: EventBusProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> AutomationUpdateResult:
    previous = await database_automations.get_automation(automation_id, user_id)
    abandoned_run_ids: tuple[str, ...] = ()
    abandoned_owner_task_ids: tuple[str, ...] = ()
    if payload.get("enabled") is False:
        updated, run_ids, owner_task_id_values = (
            await database_automations.update_automation_and_abandon_disabled_runs(
                automation_id,
                user_id,
                payload,
                finished_at_ms=epoch_ms(),
                status_message="disabled",
            )
        )
        abandoned_run_ids = tuple(run_ids)
        owner_task_ids = require_automation_identifier_list(
            owner_task_id_values,
            label="abandoned owner task ids",
        )
        abandoned_owner_task_ids = tuple(owner_task_ids)
        await finalize_abandoned_automation_owner_task_ids(
            task_registry,
            owner_task_ids,
            error_message="Automation run disabled.",
        )
    else:
        updated = await database_automations.update_automation(automation_id, user_id, payload)
    if updated is None:
        return AutomationUpdateResult(automation=None)
    propagated = await _propagate_updated_automation_settings(
        database_automations,
        automation_id=automation_id,
        user_id=user_id,
        previous=previous,
        updated=updated,
        event_bus=event_bus,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
    )
    return AutomationUpdateResult(
        automation=propagated.automation,
        conversation_versions=propagated.conversation_versions,
        abandoned_run_ids=abandoned_run_ids,
        abandoned_owner_task_ids=abandoned_owner_task_ids,
    )
