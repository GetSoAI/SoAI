"""SoAI - WebUI API route registrars [backend/features/api/route_modules_webui.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from features.api.routes.webui import (
    absolute_paths_routes,
    auth,
    auth_session_rotation,
    chat_preset_routes,
    chat_prompt_history_routes,
    conversation_agent_routes,
    conversation_archived_routes,
    conversation_bulk_delete_routes,
    conversation_clone_routes,
    conversation_comparison_preflight_routes,
    conversation_detail_routes,
    conversation_draft_routes,
    conversation_input_queue_routes,
    conversation_interaction_routes,
    conversation_json_export_routes,
    conversation_list_create_routes,
    conversation_mcp_config_endpoints,
    conversation_mcp_tools_routes,
    conversation_message_read_routes,
    conversation_message_write_routes,
    conversation_pdf_export_routes,
    conversation_settings_route,
    conversation_stream_status_route,
    conversation_update_routes,
    conversation_web_search_endpoints,
    conversation_workspace_path_route,
    key_assignment_routes,
    keys_endpoints,
    knowledge_catalog_routes,
    mcp_access_tokens_endpoints,
    media_preview_routes,
    messaging_account_mcp_routes,
    messaging_account_routes,
    notifications_routes,
    prompts,
    sessions_endpoints,
    soai_links_routes,
    soai_path_content_routes,
    soai_path_operation_routes,
    terminal_policy_routes,
    tool_icon_catalog,
    username_routes,
    users_admin_file_browser_routes,
    users_admin_routes,
    users_self_memory_routes,
    users_self_routes,
    wallpaper_delete_routes,
    wallpaper_download_routes,
    wallpaper_read_routes,
    wallpaper_upload_routes,
)
from features.api.routes.webui.calendar.routes import register_calendar_routes
from features.api.routes.webui.conversation_attachments import (
    conversation_attachment_routes,
)
from features.api.routes.webui.conversation_rag.config import config_routes
from features.api.routes.webui.conversation_rag.documents import (
    delete_routes,
    list_routes,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload import (
    batch_upload_routes,
)
from features.api.routes.webui.conversation_rag.documents.upload import upload_routes
from features.api.routes.webui.conversation_rag.file_explorer_ingest import (
    file_explorer_ingest_routes,
)
from features.api.routes.webui.conversation_rag.search import search_routes
from features.api.routes.webui.mail.routes import register_mail_routes
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ()

WEBUI_ROUTE_REGISTRARS: tuple[Callable[[ApiRouters], None], ...] = (
    auth.register_routes,
    auth_session_rotation.register_routes,
    chat_prompt_history_routes.register_routes,
    chat_preset_routes.register_routes,
    conversation_interaction_routes.register_routes,
    conversation_mcp_tools_routes.register_routes,
    conversation_mcp_config_endpoints.register_routes,
    config_routes.register_routes,
    list_routes.register_routes,
    upload_routes.register_routes,
    batch_upload_routes.register_routes,
    delete_routes.register_routes,
    file_explorer_ingest_routes.register_routes,
    search_routes.register_routes,
    conversation_list_create_routes.register_routes,
    conversation_archived_routes.register_routes,
    conversation_bulk_delete_routes.register_routes,
    conversation_clone_routes.register_routes,
    conversation_detail_routes.register_routes,
    conversation_message_read_routes.register_routes,
    conversation_message_write_routes.register_routes,
    conversation_comparison_preflight_routes.register_routes,
    conversation_json_export_routes.register_routes,
    conversation_pdf_export_routes.register_routes,
    conversation_stream_status_route.register_routes,
    conversation_attachment_routes.register_routes,
    conversation_draft_routes.register_routes,
    conversation_input_queue_routes.register_routes,
    conversation_agent_routes.register_routes,
    conversation_workspace_path_route.register_routes,
    conversation_settings_route.register_routes,
    conversation_update_routes.register_routes,
    conversation_web_search_endpoints.register_routes,
    knowledge_catalog_routes.register_routes,
    key_assignment_routes.register_routes,
    keys_endpoints.register_routes,
    mcp_access_tokens_endpoints.register_routes,
    prompts.register_routes,
    sessions_endpoints.register_routes,
    notifications_routes.register_routes,
    terminal_policy_routes.register_routes,
    tool_icon_catalog.register_routes,
    media_preview_routes.register_routes,
    messaging_account_routes.register_routes,
    messaging_account_mcp_routes.register_routes,
    absolute_paths_routes.register_routes,
    soai_links_routes.register_routes,
    soai_path_content_routes.register_routes,
    soai_path_operation_routes.register_routes,
    users_self_memory_routes.register_routes,
    users_self_routes.register_routes,
    username_routes.register_routes,
    users_admin_file_browser_routes.register_routes,
    users_admin_routes.register_routes,
    wallpaper_delete_routes.register_routes,
    wallpaper_download_routes.register_routes,
    wallpaper_read_routes.register_routes,
    wallpaper_upload_routes.register_routes,
    register_mail_routes,
    register_calendar_routes,
)
