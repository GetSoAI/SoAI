"""SoAI - Automation execution settings preparation [backend/features/automation/execution_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.settings_types import AgentSettings
from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.automation.automation_identifiers import (
    build_automation_run_cancellation_id,
    build_automation_run_trace_id,
)
from core.errors.exceptions import ValidationError
from core.runtime.request_context import RequestContext
from core.runtime.request_context_agent_fields import apply_agent_runtime_context_fields

__all__ = ("build_automation_request_context",)


def build_automation_request_context(
    *,
    user_id: int,
    run_id: str,
    requested_model: str,
    agent_settings: AgentSettings,
    interactive_tool_approval: bool,
) -> RequestContext:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValidationError("Automation request context requires a non-empty run_id.")
    context = RequestContext(
        trace_id=build_automation_run_trace_id(normalized_run_id),
        client_ip="internal",
        user_id=user_id,
        task_id=normalized_run_id,
        cancellation_id=build_automation_run_cancellation_id(normalized_run_id),
        interactive_tool_approval=interactive_tool_approval,
    )
    apply_agent_runtime_context_fields(
        context=context,
        settings=agent_settings,
        requested_model=requested_model,
        turn_scope=TURN_SCOPE_ROOT,
    )
    return context
