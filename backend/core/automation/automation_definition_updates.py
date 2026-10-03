"""SoAI - Automation definition update lifecycle [backend/core/automation/automation_definition_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_conversation_model_settings import (
    resolve_automation_conversation_model_settings,
)
from core.automation.automation_mutation_results import AutomationUpdateResult
from core.errors.exceptions import AutomationRevisionConflictError

if TYPE_CHECKING:
    from core.automation.protocols_database import DatabaseAutomationsProtocol
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("update_automation_definition",)


async def update_automation_definition(
    database_automations: DatabaseAutomationsProtocol,
    *,
    automation_id: str,
    user_id: int,
    payload: JSONDict,
    expected_revision: str | None,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> AutomationUpdateResult:
    for attempt in range(3):
        prepared = await database_automations.prepare_automation_update(
            automation_id,
            user_id,
            payload,
            expected_revision=expected_revision,
        )
        if prepared is None:
            return AutomationUpdateResult(automation=None)
        conversation_model_settings = None
        if prepared.model_settings is not None:
            conversation_model_settings = await resolve_automation_conversation_model_settings(
                user_id=user_id,
                model_settings=prepared.model_settings,
                database_chat_identity_defaults=database_chat_identity_defaults,
                database_chat_model_defaults=database_chat_model_defaults,
            )
        try:
            return await database_automations.commit_automation_update(
                prepared,
                conversation_model_settings,
            )
        except AutomationRevisionConflictError:
            if expected_revision is not None or attempt == 2:
                raise
    raise AutomationRevisionConflictError(
        "Automation changed repeatedly while preparing its settings."
    )
