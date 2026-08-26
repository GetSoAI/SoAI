"""SoAI - Canonical V1 database schema object creation [backend/database/v1_schema_objects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.tasks.enums import TASK_STATUS_SQL_VALUES
from core.tasks.status_policy import ACTIVE_TASK_STATUS_VALUES
from core.tasks.type_catalog import TaskTypeCatalog
from database.repositories.users.context_compaction_metric_events import (
    sync_reconcile_context_compaction_metric_events,
)
from database.schema_scripts.agent_turns import apply_agent_turns_schema
from database.schema_scripts.api_access_credentials_schema import (
    apply_api_access_credentials_schema,
)
from database.schema_scripts.assistant_message_events import (
    apply_assistant_message_events_schema,
)
from database.schema_scripts.auth_failure_buckets import apply_auth_failure_buckets_schema
from database.schema_scripts.authoritative_plugin_state.outbox import (
    apply_authoritative_plugin_state_outbox_schema,
)
from database.schema_scripts.automation import apply_automation_schema
from database.schema_scripts.calendar import apply_calendar_schema
from database.schema_scripts.chat_prompt_history import apply_chat_prompt_history_schema
from database.schema_scripts.chat_tool_calls import apply_chat_tool_calls_schema
from database.schema_scripts.context_compaction_metric_events import (
    apply_context_compaction_metric_events_schema,
)
from database.schema_scripts.conversation_attachments import (
    apply_conversation_attachments_schema,
)
from database.schema_scripts.conversation_drafts import apply_conversation_drafts_schema
from database.schema_scripts.conversation_inputs import apply_conversation_inputs_schema
from database.schema_scripts.domain_event_outbox import apply_domain_event_outbox_schema
from database.schema_scripts.external_accounts import apply_external_accounts_schema
from database.schema_scripts.hardware_soaibench import apply_hardware_soaibench_schema
from database.schema_scripts.licensing import apply_licensing_schema
from database.schema_scripts.mail import apply_mail_schema
from database.schema_scripts.memory import apply_memory_schema
from database.schema_scripts.messaging import apply_messaging_account_schema
from database.schema_scripts.messaging_delivery import apply_messaging_delivery_schema
from database.schema_scripts.messaging_ingress import apply_messaging_ingress_schema
from database.schema_scripts.messaging_interactions import apply_messaging_interaction_schema
from database.schema_scripts.metrics_files_tasks import apply_metrics_files_tasks_schema
from database.schema_scripts.models_schema import apply_models_schema
from database.schema_scripts.mutation_admission import apply_mutation_admission_schema
from database.schema_scripts.notifications import apply_notifications_schema
from database.schema_scripts.openai_chat_completions import (
    apply_openai_chat_completions_schema,
)
from database.schema_scripts.openai_conversations import apply_openai_conversations_schema
from database.schema_scripts.openai_responses import apply_openai_responses_schema
from database.schema_scripts.password_vault import apply_password_vault_schema
from database.schema_scripts.plugin_catalog_schema import apply_plugin_catalog_schema
from database.schema_scripts.plugin_clone_transactions import apply_plugin_clone_schema
from database.schema_scripts.rag_storage import apply_rag_storage_schema
from database.schema_scripts.read_video import apply_read_video_schema
from database.schema_scripts.system_operations import apply_system_operations_schema
from database.schema_scripts.task_interaction_secrets import (
    apply_task_interaction_secrets_schema,
)
from database.schema_scripts.tool_call_live_events import apply_tool_call_live_events_schema
from database.schema_scripts.webui_accounts_schema import apply_webui_accounts_schema
from database.schema_scripts.webui_chat_presets_schema import (
    apply_webui_chat_presets_schema,
)
from database.schema_scripts.webui_chat_storage_schema import apply_webui_chat_storage_schema
from database.schema_scripts.webui_mutations_schema import apply_webui_mutations_schema
from database.schema_scripts.webui_sessions_schema import apply_webui_sessions_schema
from database.schema_scripts.webui_title_search_schema import (
    apply_webui_title_search_schema,
)

__all__ = ("apply_current_v1_schema_objects",)


def _build_sql_check_clause(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def apply_current_v1_schema_objects(
    conn: sqlite3.Connection,
    task_catalog: TaskTypeCatalog,
) -> None:
    task_type_check = _build_sql_check_clause(task_catalog.values)
    task_status_check = _build_sql_check_clause(TASK_STATUS_SQL_VALUES)
    active_task_status_check = _build_sql_check_clause(ACTIVE_TASK_STATUS_VALUES)
    apply_plugin_catalog_schema(conn)
    apply_webui_accounts_schema(conn)
    apply_api_access_credentials_schema(conn)
    apply_webui_chat_storage_schema(conn)
    apply_webui_chat_presets_schema(conn)
    apply_webui_sessions_schema(conn)
    apply_webui_mutations_schema(conn)
    apply_webui_title_search_schema(conn)
    apply_external_accounts_schema(conn)
    apply_mail_schema(conn)
    apply_calendar_schema(conn)
    apply_models_schema(conn)
    apply_notifications_schema(conn)
    apply_auth_failure_buckets_schema(conn)
    apply_password_vault_schema(conn)
    apply_authoritative_plugin_state_outbox_schema(conn)
    apply_automation_schema(conn)
    apply_domain_event_outbox_schema(conn)
    apply_licensing_schema(conn)
    apply_metrics_files_tasks_schema(
        conn,
        task_type_check=task_type_check,
        task_status_check=task_status_check,
        active_task_status_check=active_task_status_check,
    )
    apply_task_interaction_secrets_schema(conn)
    apply_mutation_admission_schema(conn)
    apply_plugin_clone_schema(conn)
    apply_hardware_soaibench_schema(conn)
    apply_openai_conversations_schema(conn)
    apply_openai_responses_schema(conn)
    apply_openai_chat_completions_schema(conn)
    apply_rag_storage_schema(conn)
    apply_chat_tool_calls_schema(conn)
    apply_context_compaction_metric_events_schema(conn)
    sync_reconcile_context_compaction_metric_events(conn)
    apply_tool_call_live_events_schema(conn)
    apply_assistant_message_events_schema(conn)
    apply_agent_turns_schema(conn)
    apply_conversation_inputs_schema(conn)
    apply_chat_prompt_history_schema(conn)
    apply_messaging_account_schema(conn)
    apply_messaging_ingress_schema(conn)
    apply_messaging_delivery_schema(conn)
    apply_messaging_interaction_schema(conn)
    apply_conversation_attachments_schema(conn)
    apply_conversation_drafts_schema(conn)
    apply_memory_schema(conn)
    apply_read_video_schema(conn)
    apply_system_operations_schema(conn)
