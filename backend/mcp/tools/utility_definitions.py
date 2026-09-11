"""SoAI - MCP utility tool definitions [backend/mcp/tools/utility_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.utility_tool_definitions.apply_patch import (
    build_apply_patch_tool_definitions,
)
from mcp.tools.utility_tool_definitions.ask_user import build_ask_user_tool_definitions
from mcp.tools.utility_tool_definitions.automation import (
    build_automation_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_action_wait_and_select import (
    build_browser_action_wait_and_select_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_actions import (
    build_browser_actions_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_autofill import (
    build_browser_autofill_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_dialog import (
    build_browser_dialog_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_downloads import (
    build_browser_downloads_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_drag import (
    build_browser_drag_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_eval import (
    build_browser_eval_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_logs import (
    build_browser_logs_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_management import (
    build_browser_management_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_navigation import (
    build_browser_navigation_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_pdf import (
    build_browser_pdf_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_profiles import (
    build_browser_profiles_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_screenshot import (
    build_browser_screenshot_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_scroll import (
    build_browser_scroll_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_snapshot import (
    build_browser_snapshot_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_status import (
    build_browser_status_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_tabs import (
    build_browser_tabs_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_upload_file import (
    build_browser_upload_file_tool_definitions,
)
from mcp.tools.utility_tool_definitions.calculator import (
    build_calculator_tool_definitions,
)
from mcp.tools.utility_tool_definitions.crypto import build_crypto_tool_definitions
from mcp.tools.utility_tool_definitions.datetime_current import (
    build_datetime_current_tool_definitions,
)
from mcp.tools.utility_tool_definitions.generate_image import (
    build_generate_image_tool_definitions,
)
from mcp.tools.utility_tool_definitions.glob_files import (
    build_glob_files_tool_definitions,
)
from mcp.tools.utility_tool_definitions.grep_files import (
    build_grep_files_tool_definitions,
)
from mcp.tools.utility_tool_definitions.hardware_benchmark import (
    build_hardware_benchmark_tool_definitions,
)
from mcp.tools.utility_tool_definitions.hardware_control import (
    build_hardware_control_tool_definitions,
)
from mcp.tools.utility_tool_definitions.hardware_snapshot import (
    build_hardware_snapshot_tool_definitions,
)
from mcp.tools.utility_tool_definitions.http_request import (
    build_http_request_tool_definitions,
)
from mcp.tools.utility_tool_definitions.list_dir import build_list_dir_tool_definitions
from mcp.tools.utility_tool_definitions.mcp_resource_read import (
    build_mcp_resource_read_tool_definitions,
)
from mcp.tools.utility_tool_definitions.mcp_resource_templates_list import (
    build_mcp_resource_templates_list_tool_definitions,
)
from mcp.tools.utility_tool_definitions.mcp_resources_list import (
    build_mcp_resources_list_tool_definitions,
)
from mcp.tools.utility_tool_definitions.memory import build_memory_tool_definitions
from mcp.tools.utility_tool_definitions.memory_conversation_history import (
    build_memory_conversation_history_tool_definitions,
)
from mcp.tools.utility_tool_definitions.message_parse import (
    build_message_parse_tool_definitions,
)
from mcp.tools.utility_tool_definitions.news import build_news_tool_definitions
from mcp.tools.utility_tool_definitions.notify_user import (
    build_notify_user_tool_definitions,
)
from mcp.tools.utility_tool_definitions.plan_get import build_plan_get_tool_definitions
from mcp.tools.utility_tool_definitions.plan_write import (
    build_plan_write_tool_definitions,
)
from mcp.tools.utility_tool_definitions.random_generate import (
    build_random_generate_tool_definitions,
)
from mcp.tools.utility_tool_definitions.read_audio import (
    build_read_audio_tool_definitions,
)
from mcp.tools.utility_tool_definitions.read_document import (
    build_read_document_tool_definitions,
)
from mcp.tools.utility_tool_definitions.read_file import (
    build_read_file_tool_definitions,
)
from mcp.tools.utility_tool_definitions.read_image import (
    build_read_image_tool_definitions,
)
from mcp.tools.utility_tool_definitions.read_video import (
    build_read_video_tool_definitions,
)
from mcp.tools.utility_tool_definitions.replace_in_file import (
    build_replace_in_file_tool_definitions,
)
from mcp.tools.utility_tool_definitions.rss_read import build_rss_read_tool_definitions
from mcp.tools.utility_tool_definitions.shell import (
    build_shell_tool_definitions,
)
from mcp.tools.utility_tool_definitions.shell_output import (
    build_shell_output_tool_definitions,
)
from mcp.tools.utility_tool_definitions.shell_write_stdin import (
    build_shell_write_stdin_tool_definitions,
)
from mcp.tools.utility_tool_definitions.soai_documentation import (
    build_soai_documentation_tool_definitions,
)
from mcp.tools.utility_tool_definitions.stop_conversation import (
    build_stop_conversation_tool_definitions,
)
from mcp.tools.utility_tool_definitions.subagents import build_subagent_tool_definitions
from mcp.tools.utility_tool_definitions.text_stats import (
    build_text_stats_tool_definitions,
)
from mcp.tools.utility_tool_definitions.todo_write import (
    build_todo_write_tool_definitions,
)
from mcp.tools.utility_tool_definitions.unit_convert import (
    build_unit_convert_tool_definitions,
)
from mcp.tools.utility_tool_definitions.vault_delete import (
    build_vault_delete_tool_definitions,
)
from mcp.tools.utility_tool_definitions.vault_list import (
    build_vault_list_tool_definitions,
)
from mcp.tools.utility_tool_definitions.vault_login_request import (
    build_vault_login_request_tool_definitions,
)
from mcp.tools.utility_tool_definitions.vault_search import (
    build_vault_search_tool_definitions,
)
from mcp.tools.utility_tool_definitions.vault_secret_request import (
    build_vault_secret_request_tool_definitions,
)
from mcp.tools.utility_tool_definitions.wait import build_wait_tool_definitions
from mcp.tools.utility_tool_definitions.weather import (
    build_weather_tool_definitions,
)
from mcp.tools.utility_tool_definitions.write_file import (
    build_write_file_tool_definitions,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_conversation_utility_tool_definitions",
    "build_internal_utility_tool_definitions",
    "build_public_utility_tool_definitions",
)


def build_public_utility_tool_definitions() -> dict[str, JSONDict]:
    merged: dict[str, JSONDict] = {}
    for _label, definitions in (
        ("subagents", build_subagent_tool_definitions()),
        ("browser_navigation", build_browser_navigation_tool_definitions()),
        ("browser_snapshot", build_browser_snapshot_tool_definitions()),
        ("browser_actions", build_browser_actions_tool_definitions()),
        ("browser_wait_and_select", build_browser_action_wait_and_select_tool_definitions()),
        ("browser_autofill", build_browser_autofill_tool_definitions()),
        ("browser_scroll", build_browser_scroll_tool_definitions()),
        ("browser_drag", build_browser_drag_tool_definitions()),
        ("browser_upload_file", build_browser_upload_file_tool_definitions()),
        ("browser_eval", build_browser_eval_tool_definitions()),
        ("browser_screenshot", build_browser_screenshot_tool_definitions()),
        ("browser_management", build_browser_management_tool_definitions()),
        ("browser_tabs", build_browser_tabs_tool_definitions()),
        ("browser_logs", build_browser_logs_tool_definitions()),
        ("browser_profiles", build_browser_profiles_tool_definitions()),
        ("browser_status", build_browser_status_tool_definitions()),
        ("browser_pdf", build_browser_pdf_tool_definitions()),
        ("browser_dialog", build_browser_dialog_tool_definitions()),
        ("browser_downloads", build_browser_downloads_tool_definitions()),
        ("read_audio", build_read_audio_tool_definitions()),
        ("ask_user", build_ask_user_tool_definitions()),
        ("vault_secret_request", build_vault_secret_request_tool_definitions()),
        ("vault_login_request", build_vault_login_request_tool_definitions()),
        ("vault_list", build_vault_list_tool_definitions()),
        ("vault_search", build_vault_search_tool_definitions()),
        ("vault_delete", build_vault_delete_tool_definitions()),
        ("automation", build_automation_tool_definitions()),
        ("calculator", build_calculator_tool_definitions()),
        ("rss_read", build_rss_read_tool_definitions()),
        ("news", build_news_tool_definitions()),
        ("weather", build_weather_tool_definitions()),
        ("datetime_current", build_datetime_current_tool_definitions()),
        ("wait", build_wait_tool_definitions()),
        ("random_generate", build_random_generate_tool_definitions()),
        ("crypto", build_crypto_tool_definitions()),
        ("text_stats", build_text_stats_tool_definitions()),
        ("unit_convert", build_unit_convert_tool_definitions()),
        ("message_parse", build_message_parse_tool_definitions()),
        ("generate_image", build_generate_image_tool_definitions()),
        ("notify_user", build_notify_user_tool_definitions()),
        ("hardware_snapshot", build_hardware_snapshot_tool_definitions()),
        ("shell", build_shell_tool_definitions()),
        ("shell_output", build_shell_output_tool_definitions()),
        ("shell_write_stdin", build_shell_write_stdin_tool_definitions()),
        ("read_file", build_read_file_tool_definitions()),
        ("read_image", build_read_image_tool_definitions()),
        ("read_video", build_read_video_tool_definitions()),
        ("read_document", build_read_document_tool_definitions()),
        ("list_dir", build_list_dir_tool_definitions()),
        ("grep_files", build_grep_files_tool_definitions()),
        ("apply_patch", build_apply_patch_tool_definitions()),
        ("todo_write", build_todo_write_tool_definitions()),
        ("plan_write", build_plan_write_tool_definitions()),
        ("plan_get", build_plan_get_tool_definitions()),
        ("mcp_resources_list", build_mcp_resources_list_tool_definitions()),
        ("mcp_resource_templates_list", build_mcp_resource_templates_list_tool_definitions()),
        ("mcp_resource_read", build_mcp_resource_read_tool_definitions()),
        ("replace_in_file", build_replace_in_file_tool_definitions()),
        ("write_file", build_write_file_tool_definitions()),
        ("glob_files", build_glob_files_tool_definitions()),
        ("http_request", build_http_request_tool_definitions()),
        ("memory", build_memory_tool_definitions()),
        ("memory_conversation_history", build_memory_conversation_history_tool_definitions()),
    ):
        merged.update(definitions)
    return merged


def build_conversation_utility_tool_definitions() -> dict[str, JSONDict]:
    merged = build_public_utility_tool_definitions()
    merged.update(build_soai_documentation_tool_definitions())
    merged.update(build_stop_conversation_tool_definitions())
    return merged


def build_internal_utility_tool_definitions() -> dict[str, JSONDict]:
    merged = build_conversation_utility_tool_definitions()
    merged.update(build_hardware_benchmark_tool_definitions())
    merged.update(build_hardware_control_tool_definitions())
    return merged
