"""SoAI - Status preview payload variant keys [backend/features/assistant_timeline/status_preview_payload_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "phase_preview_key_variants",
    "tool_preview_key_variants_detail",
    "tool_preview_key_variants_plain",
    "web_search_preview_key_variants_detail",
    "web_search_preview_key_variants_plain",
)

_TOOLS_WITH_DETAIL: tuple[str, ...] = (
    "read_file",
    "read_image",
    "read_video",
    "read_document",
    "shell",
    "automation_create",
    "automation_update",
    "automation_run_enqueue",
    "automation_run_get",
    "automation_run_wait",
    "knowledge_search",
    "knowledge_ingest",
    "knowledge_reindex",
    "web_fetch",
    "knowledge_web_fetch",
    "http_request",
    "rss_read",
    "news",
    "calculator",
    "hardware_snapshot",
    "unit_convert",
    "replace_in_file",
    "shell_output_read",
    "shell_output_search",
    "shell_write_stdin",
    "todo_write",
    "plan_get",
    "plan_write",
    "notify_user",
    "mcp_resource_read",
    "list_dir",
    "glob_files",
    "grep_files",
    "write_file",
)


def _to_detail_key(variant: str) -> str:
    normalized = str(variant or "").strip()
    if not normalized:
        return normalized
    parts = normalized.split(".")
    if len(parts) < 2:
        return normalized
    return ".".join((*parts[:-1], "detail", parts[-1]))


def tool_preview_key_variants_plain() -> dict[str, tuple[str, ...]]:
    return {
        "read_file": (
            "chat.stream.preview.tools.read_file.1",
            "chat.stream.preview.tools.read_file.2",
        ),
        "read_image": (
            "chat.stream.preview.tools.read_image.1",
            "chat.stream.preview.tools.read_image.2",
        ),
        "read_video": (
            "chat.stream.preview.tools.read_video.1",
            "chat.stream.preview.tools.read_video.2",
        ),
        "read_document": (
            "chat.stream.preview.tools.read_document.1",
            "chat.stream.preview.tools.read_document.2",
        ),
        "read_audio": ("chat.stream.preview.tools.read_audio.1",),
        "shell": (
            "chat.stream.preview.tools.shell.1",
            "chat.stream.preview.tools.shell.2",
        ),
        "ask_user": (
            "chat.stream.preview.tools.ask_user.1",
            "chat.stream.preview.tools.ask_user.2",
        ),
        "vault_secret_request": ("chat.stream.preview.tools.vault_secret_request.1",),
        "subagent_spawn": ("chat.stream.preview.tools.subagent_spawn.1",),
        "subagent_observe": ("chat.stream.preview.tools.subagent_observe.1",),
        "subagent_cancel": ("chat.stream.preview.tools.subagent_cancel.1",),
        "automation_create": ("chat.stream.preview.tools.automation_create.1",),
        "automation_update": ("chat.stream.preview.tools.automation_update.1",),
        "automation_run_enqueue": ("chat.stream.preview.tools.automation_run_enqueue.1",),
        "automation_run_get": ("chat.stream.preview.tools.automation_run_get.1",),
        "automation_run_wait": ("chat.stream.preview.tools.automation_run_wait.1",),
        "knowledge_search": ("chat.stream.preview.tools.knowledge_search.1",),
        "knowledge_ingest": ("chat.stream.preview.tools.knowledge_ingest.1",),
        "knowledge_config_get": ("chat.stream.preview.tools.knowledge_config_get.1",),
        "knowledge_list": ("chat.stream.preview.tools.knowledge_list.1",),
        "knowledge_reindex": (
            "chat.stream.preview.tools.knowledge_reindex.1",
            "chat.stream.preview.tools.knowledge_reindex.2",
        ),
        "mail_accounts_list": ("chat.stream.preview.tools.mail_accounts_list.1",),
        "mail_folders_list": ("chat.stream.preview.tools.mail_folders_list.1",),
        "mail_messages_list": ("chat.stream.preview.tools.mail_messages_list.1",),
        "mail_message_read": ("chat.stream.preview.tools.mail_message_read.1",),
        "mail_attachment_download": ("chat.stream.preview.tools.mail_attachment_download.1",),
        "mail_account_sync": ("chat.stream.preview.tools.mail_account_sync.1",),
        "mail_messages_remote_search": ("chat.stream.preview.tools.mail_messages_remote_search.1",),
        "mail_folder_backfill": ("chat.stream.preview.tools.mail_folder_backfill.1",),
        "mail_message_compose": ("chat.stream.preview.tools.mail_message_compose.1",),
        "mail_message_update": ("chat.stream.preview.tools.mail_message_update.1",),
        "mail_folder_update": ("chat.stream.preview.tools.mail_folder_update.1",),
        "calendar_accounts_list": ("chat.stream.preview.tools.calendar_accounts_list.1",),
        "calendar_calendars_list": ("chat.stream.preview.tools.calendar_calendars_list.1",),
        "calendar_account_sync": ("chat.stream.preview.tools.calendar_account_sync.1",),
        "calendar_window_sync": ("chat.stream.preview.tools.calendar_window_sync.1",),
        "calendar_events_list": ("chat.stream.preview.tools.calendar_events_list.1",),
        "calendar_event_read": ("chat.stream.preview.tools.calendar_event_read.1",),
        "calendar_event_update": ("chat.stream.preview.tools.calendar_event_update.1",),
        "calendar_invite_respond": ("chat.stream.preview.tools.calendar_invite_respond.1",),
        "web_fetch": (
            "chat.stream.preview.tools.web_fetch.1",
            "chat.stream.preview.tools.web_fetch.2",
        ),
        "knowledge_web_fetch": ("chat.stream.preview.tools.knowledge_web_fetch.1",),
        "http_request": (
            "chat.stream.preview.tools.http_request.1",
            "chat.stream.preview.tools.http_request.2",
        ),
        "rss_read": ("chat.stream.preview.tools.rss_read.1",),
        "news": ("chat.stream.preview.tools.news.1",),
        "weather": ("chat.stream.preview.tools.weather.1",),
        "random_generate": ("chat.stream.preview.tools.random_generate.1",),
        "hash": ("chat.stream.preview.tools.hash.1",),
        "base64": ("chat.stream.preview.tools.base64.1",),
        "text_stats": ("chat.stream.preview.tools.text_stats.1",),
        "message_parse": ("chat.stream.preview.tools.message_parse.1",),
        "generate_image": ("chat.stream.preview.tools.generate_image.1",),
        "calculator": ("chat.stream.preview.tools.calculator.1",),
        "datetime_current": ("chat.stream.preview.tools.datetime_current.1",),
        "hardware_snapshot": ("chat.stream.preview.tools.hardware_snapshot.1",),
        "hardware_benchmark": ("chat.stream.preview.tools.hardware_benchmark.1",),
        "hardware_control": ("chat.stream.preview.tools.hardware_control.1",),
        "unit_convert": ("chat.stream.preview.tools.unit_convert.1",),
        "wait": ("chat.stream.preview.tools.wait.1",),
        "stop_conversation": ("chat.stream.preview.tools.stop_conversation.1",),
        "replace_in_file": ("chat.stream.preview.tools.replace_in_file.1",),
        "shell_output_read": ("chat.stream.preview.tools.shell_output_read.1",),
        "shell_output_search": ("chat.stream.preview.tools.shell_output_search.1",),
        "shell_write_stdin": ("chat.stream.preview.tools.shell_write_stdin.1",),
        "todo_write": ("chat.stream.preview.tools.todo_write.1",),
        "plan_get": ("chat.stream.preview.tools.plan_get.1",),
        "plan_write": ("chat.stream.preview.tools.plan_write.1",),
        "notify_user": ("chat.stream.preview.tools.notify_user.1",),
        "mcp_resources_list": ("chat.stream.preview.tools.mcp_resources_list.1",),
        "mcp_resource_templates_list": ("chat.stream.preview.tools.mcp_resource_templates_list.1",),
        "mcp_resource_read": ("chat.stream.preview.tools.mcp_resource_read.1",),
        "list_dir": ("chat.stream.preview.tools.list_dir.1",),
        "glob_files": ("chat.stream.preview.tools.glob_files.1",),
        "grep_files": ("chat.stream.preview.tools.grep_files.1",),
        "write_file": ("chat.stream.preview.tools.write_file.1",),
        "apply_patch": ("chat.stream.preview.tools.apply_patch.1",),
    }


def tool_preview_key_variants_detail() -> dict[str, tuple[str, ...]]:
    base = tool_preview_key_variants_plain()
    variants: dict[str, tuple[str, ...]] = {}
    for tool_name in _TOOLS_WITH_DETAIL:
        tool_variants = base.get(tool_name)
        if tool_variants is None:
            continue
        variants[tool_name] = tuple(_to_detail_key(key) for key in tool_variants)
    return variants


def web_search_preview_key_variants_plain() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.web_search.1",
        "chat.stream.preview.tools.web_search.2",
    )


def web_search_preview_key_variants_detail() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.web_search.detail.1",
        "chat.stream.preview.tools.web_search.detail.2",
    )


def phase_preview_key_variants() -> dict[str, tuple[str, ...]]:
    return {
        "waiting_for_user": (
            "chat.stream.preview.phases.waiting_for_user.1",
            "chat.stream.preview.phases.waiting_for_user.2",
        ),
        "running_tool": (
            "chat.stream.preview.phases.running_tool.1",
            "chat.stream.preview.phases.running_tool.2",
        ),
        "context_compaction": ("chat.stream.preview.phases.context_compaction.1",),
        "thinking": (
            "chat.stream.preview.phases.thinking.1",
            "chat.stream.preview.phases.thinking.2",
        ),
        "processing": (
            "chat.stream.preview.phases.processing.1",
            "chat.stream.preview.phases.processing.2",
        ),
        "loading": (
            "chat.stream.preview.phases.loading.1",
            "chat.stream.preview.phases.loading.2",
        ),
        "responding": (
            "chat.stream.preview.phases.responding.1",
            "chat.stream.preview.phases.responding.2",
        ),
        "working": (
            "chat.stream.preview.phases.working.1",
            "chat.stream.preview.phases.working.2",
        ),
    }
