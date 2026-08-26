"""SoAI - Core API route module registrars [backend/features/api/route_modules.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from features.api.route_modules_webui import WEBUI_ROUTE_REGISTRARS
from features.api.routes.actions import actions, software
from features.api.routes.anthropic import messages
from features.api.routes.automations import (
    definition_endpoints,
    mcp_tools_routes,
    window_routes,
)
from features.api.routes.backups import backup_routes
from features.api.routes.configs import configs
from features.api.routes.file_explorer import (
    copy_routes,
    delete_endpoints,
    directory_listing_routes,
    listing_routes,
    move_routes,
    preview_routes,
    query_endpoints,
    transfer_routes,
    write_routes,
)
from features.api.routes.hardware import (
    hardware_capabilities_routes,
    hardware_export_routes,
    hardware_gpu_endpoints,
    hardware_gpu_soaibench_routes,
    hardware_history_routes,
    hardware_process_routes,
    hardware_snapshot_routes,
)
from features.api.routes.mcp.routes import (
    management_catalog_routes,
    management_client_routes,
    management_oauth_routes,
    management_search_api_key_routes,
    management_server_endpoints,
    management_status_routes,
    server_mode,
)
from features.api.routes.messaging import messaging_routes
from features.api.routes.metrics import metrics, metrics_export_routes
from features.api.routes.models import models
from features.api.routes.openai import (
    audio_speech_routes,
    audio_upload_routes,
    completions,
    embeddings,
    file_query_routes,
    file_upload_endpoints,
    images,
    images_edit_upload_routes,
    images_variation_upload_routes,
    openai_models,
)
from features.api.routes.openai.chat import endpoint, stored_endpoints, stored_messages
from features.api.routes.openai.responses import (
    auxiliary_routes,
    compact_routes,
    endpoint_family_cancel,
    endpoint_family_delete,
    endpoint_family_get,
    endpoint_family_input_items,
    responses_endpoint_routes,
)
from features.api.routes.plugins import (
    plugin_backend_routes,
    plugin_catalog_routes,
    plugin_download_routes,
    plugin_package_routes,
    plugin_provider_create_list_routes,
    plugin_provider_mutation_routes,
    plugin_upload_routes,
)
from features.api.routes.routing import routing_endpoints
from features.api.routes.system import (
    system_access_control_routes,
    system_database_operation_routes,
    system_logs_routes,
    system_meta_routes,
    system_metrics_routes,
    system_plugins_circuit_breaker_routes,
    system_power_routes,
    system_reset_routes,
    system_search_routes,
    system_security_hardening_routes,
    system_state_routes,
    system_status_routes,
)
from features.api.routes.system.events import websocket
from features.api.routes.tasks import (
    software_update_log_routes,
    task_cancel_routes,
    task_cancellation_endpoints,
    task_list_routes,
)
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("ROUTE_REGISTRARS", "get_route_registrars")

ROUTE_REGISTRARS: tuple[Callable[[ApiRouters], None], ...] = (
    actions.register_routes,
    software.register_routes,
    backup_routes.register_routes,
    configs.register_routes,
    hardware_export_routes.register_routes,
    hardware_capabilities_routes.register_routes,
    hardware_gpu_soaibench_routes.register_routes,
    hardware_gpu_endpoints.register_routes,
    hardware_process_routes.register_routes,
    hardware_snapshot_routes.register_routes,
    hardware_history_routes.register_routes,
    management_status_routes.register_routes,
    management_server_endpoints.register_routes,
    management_oauth_routes.register_routes,
    management_client_routes.register_routes,
    management_catalog_routes.register_routes,
    management_search_api_key_routes.register_routes,
    server_mode.register_routes,
    messaging_routes.register_routes,
    metrics_export_routes.register_routes,
    metrics.register_routes,
    models.register_routes,
    listing_routes.register_routes,
    directory_listing_routes.register_routes,
    query_endpoints.register_routes,
    write_routes.register_routes,
    delete_endpoints.register_routes,
    move_routes.register_routes,
    copy_routes.register_routes,
    transfer_routes.register_routes,
    preview_routes.register_routes,
    audio_upload_routes.register_routes,
    audio_speech_routes.register_routes,
    messages.register_routes,
    endpoint.register_routes,
    stored_endpoints.register_routes,
    stored_messages.register_routes,
    completions.register_routes,
    embeddings.register_routes,
    file_upload_endpoints.register_routes,
    file_query_routes.register_routes,
    images_edit_upload_routes.register_routes,
    images_variation_upload_routes.register_routes,
    images.register_routes,
    openai_models.register_routes,
    responses_endpoint_routes.register_routes,
    endpoint_family_get.register_routes,
    endpoint_family_delete.register_routes,
    endpoint_family_cancel.register_routes,
    endpoint_family_input_items.register_routes,
    auxiliary_routes.register_routes,
    compact_routes.register_routes,
    plugin_backend_routes.register_routes,
    plugin_catalog_routes.register_routes,
    plugin_download_routes.register_routes,
    plugin_package_routes.register_routes,
    plugin_provider_create_list_routes.register_routes,
    plugin_provider_mutation_routes.register_routes,
    plugin_upload_routes.register_routes,
    routing_endpoints.register_routes,
    websocket.register_routes,
    system_access_control_routes.register_routes,
    system_database_operation_routes.register_routes,
    system_reset_routes.register_routes,
    system_logs_routes.register_routes,
    system_meta_routes.register_routes,
    system_metrics_routes.register_routes,
    system_plugins_circuit_breaker_routes.register_routes,
    system_power_routes.register_routes,
    system_search_routes.register_routes,
    system_security_hardening_routes.register_routes,
    system_state_routes.register_routes,
    system_status_routes.register_routes,
    software_update_log_routes.register_routes,
    task_cancel_routes.register_routes,
    task_cancellation_endpoints.register_routes,
    task_list_routes.register_routes,
    mcp_tools_routes.register_routes,
    window_routes.register_routes,
    definition_endpoints.register_routes,
)


def get_route_registrars(
    edition_registrars: tuple[Callable[[ApiRouters], None], ...] = (),
) -> tuple[Callable[[ApiRouters], None], ...]:
    return ROUTE_REGISTRARS + WEBUI_ROUTE_REGISTRARS + edition_registrars
