"""SoAI - Orchestrator control event subscription mapping [backend/orchestrator/control/subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable

from core.events.types_base import Event
from core.events.types_models_model_events import ModelParametersRequireReloadEvent
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
    ImageEditRequestReceived,
    ImageVariationRequestReceived,
    InferenceRequestReceived,
)
from core.events.types_models_routing_commands import (
    GetRoutingConfigCommand,
    UpdateRoutingConfigCommand,
)
from core.events.types_models_routing_events import RoutingConfigChangedEvent
from core.events.types_plugins import (
    ClearQuarantineCommand,
    PluginInstallationStateChangedEvent,
    PluginLoadedEvent,
    PluginPurgedEvent,
    PluginRuntimeStateChangedEvent,
    PluginStoppedEvent,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
    StopAllPluginsCommand,
)
from core.events.types_system import ConfigReloadedEvent, SystemQuiesceEvent
from core.events.types_tasks import CancelAllTasksCommand, CancelTaskCommand
from orchestrator.control import (
    config_management,
    plugin_commands,
    request_routing,
    task_management,
)
from orchestrator.control.internal_protocols import (
    OrchestratorControlSubscriptionsProtocol,
)

__all__ = ("build_orchestrator_control_event_handlers",)


def build_orchestrator_control_event_handlers(
    control: OrchestratorControlSubscriptionsProtocol,
) -> dict[type[Event], Callable[[Event], Awaitable[None]]]:
    return {
        SystemQuiesceEvent: control.handle_system_quiesce,
        InferenceRequestReceived: functools.partial(
            request_routing.handle_inference_request,
            deps=control.request_deps,
        ),
        AudioTranscriptionRequestReceived: functools.partial(
            request_routing.handle_media_or_vision_request,
            deps=control.request_deps,
        ),
        AudioTranslationRequestReceived: functools.partial(
            request_routing.handle_media_or_vision_request,
            deps=control.request_deps,
        ),
        ImageEditRequestReceived: functools.partial(
            request_routing.handle_media_or_vision_request,
            deps=control.request_deps,
        ),
        ImageVariationRequestReceived: functools.partial(
            request_routing.handle_media_or_vision_request,
            deps=control.request_deps,
        ),
        CancelTaskCommand: functools.partial(
            task_management.handle_cancel_task,
            deps=control.task_deps,
        ),
        CancelAllTasksCommand: functools.partial(
            task_management.handle_cancel_all_tasks,
            deps=control.task_deps,
        ),
        StopAllPluginsCommand: functools.partial(
            plugin_commands.handle_stop_all_plugins,
            deps=control.plugin_deps,
        ),
        RequestPluginStopAndWaitCommand: functools.partial(
            plugin_commands.handle_plugin_stop_and_wait,
            deps=control.plugin_deps,
        ),
        RequestPluginDisableCommand: functools.partial(
            plugin_commands.handle_plugin_disable_command,
            deps=control.plugin_deps,
        ),
        RequestPluginEnableCommand: functools.partial(
            plugin_commands.handle_plugin_enable_command,
            deps=control.plugin_deps,
        ),
        PluginStoppedEvent: functools.partial(
            plugin_commands.handle_plugin_stopped,
            deps=control.plugin_deps,
        ),
        PluginLoadedEvent: functools.partial(
            plugin_commands.handle_plugin_reloaded,
            deps=control.plugin_deps,
        ),
        PluginRuntimeStateChangedEvent: functools.partial(
            plugin_commands.handle_plugin_state_change,
            deps=control.plugin_deps,
        ),
        PluginInstallationStateChangedEvent: functools.partial(
            plugin_commands.handle_plugin_state_change,
            deps=control.plugin_deps,
        ),
        RoutingConfigChangedEvent: functools.partial(
            config_management.handle_routing_config_changed,
            deps=control.config_deps,
            component_context_holder=control.component_context_holder,
        ),
        ModelParametersRequireReloadEvent: functools.partial(
            plugin_commands.handle_model_parameters_require_reload,
            deps=control.plugin_deps,
        ),
        ClearQuarantineCommand: functools.partial(
            plugin_commands.handle_clear_quarantine,
            deps=control.plugin_deps,
        ),
        PluginPurgedEvent: functools.partial(
            plugin_commands.handle_plugin_purged,
            deps=control.plugin_deps,
        ),
        GetRoutingConfigCommand: control.lifecycle.routing.handle_get_routing_config,
        UpdateRoutingConfigCommand: control.lifecycle.routing.handle_update_routing_config,
        ConfigReloadedEvent: functools.partial(
            plugin_commands.handle_plugin_config_reloaded,
            deps=control.plugin_deps,
        ),
    }
