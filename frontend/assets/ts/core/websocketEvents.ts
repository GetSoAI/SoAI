/* SoAI - Shared frontend WebSocket events [frontend/assets/ts/core/websocketEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { STREAMS } from '@core/constants.ts';
import { CAPS, HARDWARE, HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES, METRICS, MODELS, MODELS_LAST_USED, PLUGINS, PLUGINS_LAST_USED, POWER_OPERATIONS, PROMPTS, PROVIDERS, ROUTING, STATUS, VIRTUAL, WEBUI_CHAT_ACTIVITY, WEBUI_CHAT_ATTENTION, WEBUI_NOTIFICATIONS } from '@core/realtime/streammanager/resources/ids.ts';

const WEBSOCKET_MESSAGE_TYPES = Object.freeze({
    PONG: 'pong',
    LATENCY_PROBE: 'latency_probe',
    REQUEST_SNAPSHOT: 'request_snapshot',
    SET_RESOURCE_INTERESTS: 'set_resource_interests',
    SUBSCRIBE_LOG_STREAM: 'subscribe_log_stream',
    UNSUBSCRIBE_LOG_STREAM: 'unsubscribe_log_stream',
    CHAT_STREAM_START: 'chat_stream_start',
    CHAT_STREAM_CANCEL: 'chat_stream_cancel',
    CHAT_TOKEN_COUNT: 'chat_token_count',
    CONVERSATION_PRESENCE_UPDATE: 'conversation_presence_update',
    CONVERSATION_ATTENTION_MARK_SEEN: 'conversation_attention_mark_seen',
    MODEL_TEST_STREAM_START: 'model_test_stream_start',
    MODEL_TEST_STREAM_CANCEL: 'model_test_stream_cancel',
    PTY_CONNECT: 'pty_connect',
    PTY_INPUT: 'pty_input',
    PTY_RESIZE: 'pty_resize',
    PTY_DISCONNECT: 'pty_disconnect',
    UPDATE_OPENAI_API_KEY_QUOTA: 'update_openai_api_key_quota',
    UPDATE_USER_WORKSPACE_PATH: 'update_user_workspace_path',
    OPENAI_AUDIO_TRANSCRIPTION_START: 'openai_audio_transcription_start',
    OPENAI_AUDIO_TRANSCRIPTION_CHUNK: 'openai_audio_transcription_chunk',
    OPENAI_AUDIO_TRANSCRIPTION_COMMIT: 'openai_audio_transcription_commit',
    OPENAI_AUDIO_TRANSCRIPTION_CANCEL: 'openai_audio_transcription_cancel',
    OPENAI_AUDIO_SPEECH_START: 'openai_audio_speech_start',
    OPENAI_AUDIO_SPEECH_CANCEL: 'openai_audio_speech_cancel',
    OPENAI_AUDIO_SPEECH_SESSION_START: 'openai_audio_speech_session_start',
    OPENAI_AUDIO_SPEECH_SESSION_SEGMENT: 'openai_audio_speech_session_segment',
    OPENAI_AUDIO_SPEECH_SESSION_FINISH: 'openai_audio_speech_session_finish',
    OPENAI_AUDIO_SPEECH_SESSION_CANCEL: 'openai_audio_speech_session_cancel',
    OPENAI_IMAGES_GENERATION_START: 'openai_images_generation_start',
    OPENAI_IMAGES_GENERATION_CANCEL: 'openai_images_generation_cancel',
    PLUGIN_BACKEND_INSTALL: 'plugin_backend_install',
    PLUGIN_BACKEND_REMOVE: 'plugin_backend_remove',
    PLUGIN_BACKEND_UPDATE: 'plugin_backend_update',
    MODEL_DOWNLOAD: 'model_download'
});

const WEBSOCKET_EVENT_TYPES = Object.freeze({
    HARDWARE_SNAPSHOT_UPDATED: 'HardwareSnapshotUpdatedEvent',
    METRICS_UPDATED: 'MetricsUpdatedEvent',
    MODEL_DATABASE_CHANGE: 'ModelDatabaseChangeEvent',
    MODEL_LAST_USED_CHANGED: 'ModelLastUsedChangedEvent',
    MODEL_LOADED: 'ModelLoadedEvent',
    SOAI_MAIN_STATE_CHANGED: 'SoAIMainStateChangedEvent',
    POWER_OPERATION_CHANGED: 'PowerOperationChangedEvent',
    CIRCUIT_BREAKER_STATE_CHANGED: 'CircuitBreakerStateChangedEvent',
    PROCESS_LIST_UPDATED: 'ProcessListUpdatedEvent',
    MODEL_PARAMETERS_CHANGED: 'ModelParametersChangedEvent',
    MODEL_PARAMETERS_REQUIRE_RELOAD: 'ModelParametersRequireReloadEvent',
    SYSTEM_RESTART_REQUIRED: 'SystemRestartRequiredEvent',
    PROVIDER_STATUS_UPDATED: 'ProviderStatusUpdatedEvent',
    LICENSING_STATUS_CHANGED: 'LicensingStatusChangedEvent',
    PLUGIN_RUNTIME_STATE_CHANGED: 'PluginRuntimeStateChangedEvent',
    PLUGIN_INSTALLATION_STATE_CHANGED: 'PluginInstallationStateChangedEvent',
    INSTALLED_PLUGINS_CHANGED: 'InstalledPluginsChangedEvent',
    PLUGIN_LOADED: 'PluginLoadedEvent',
    PLUGIN_UNLOADED: 'PluginUnloadedEvent',
    PLUGIN_PURGED: 'PluginPurgedEvent',
    PLUGIN_LAST_USED_CHANGED: 'PluginLastUsedChangedEvent',
    ROUTING_CONFIG_CHANGED: 'RoutingConfigChangedEvent',
    GPU_CAPABILITIES_CHANGED: 'GPUCapabilitiesChangedEvent',
    GPU_SAVED_SETTINGS_CHANGED: 'GPUSavedSettingsChangedEvent',
    GPU_ACTIVE_SLOT_CHANGED: 'GPUActiveSlotChangedEvent',
    GPU_BOOT_PREFERENCE_CHANGED: 'GPUBootPreferenceChangedEvent',
    GPU_STARTUP_WARNING: 'GPUStartupWarningEvent',
    SOAIBENCH_RUN_UPDATED: 'SoAIBenchRunUpdatedEvent',
    PROMPT_LIST_UPDATED: 'PromptListUpdatedEvent',
    AUTOMATION_CREATED: 'AutomationCreatedEvent',
    AUTOMATION_UPDATED: 'AutomationUpdatedEvent',
    AUTOMATION_DELETED: 'AutomationDeletedEvent',
    AUTOMATION_RUN_CREATED: 'AutomationRunCreatedEvent',
    AUTOMATION_RUN_UPDATED: 'AutomationRunUpdatedEvent',
    TASK_CREATED: 'TaskCreatedEvent',
    TASK_PROGRESS: 'TaskProgressEvent',
    TASK_COMPLETE: 'TaskCompleteEvent',
    TASK_STATUS_CHANGED: 'TaskStatusChangedEvent',
    CONVERSATION_CREATED: 'ConversationCreatedEvent',
    CONVERSATION_UPDATED: 'ConversationUpdatedEvent',
    CONVERSATION_DELETED: 'ConversationDeletedEvent',
    CONVERSATION_DRAFT_CHANGED: 'ConversationDraftChangedEvent',
    MESSAGE_SAVED: 'MessageSavedEvent',
    CONVERSATION_ATTACHMENT_CHANGED: 'ConversationAttachmentChangedEvent',
    KNOWLEDGE_ATTACHMENT_CHANGED: 'KnowledgeAttachmentChangedEvent',
    CONVERSATION_INPUTS_CHANGED: 'ConversationInputsChangedEvent',
    CONVERSATION_INPUT_TERMINAL: 'ConversationInputTerminalEvent',
    CONVERSATION_ATTENTION_CHANGED: 'ConversationAttentionChangedEvent',
    CHAT_STREAM_EVENT: 'ChatStreamEvent',
    CHAT_STREAM_ACTIVITY_CHANGED: 'ChatStreamActivityChangedEvent',
    CHAT_STREAM_STATUS_PREVIEW: 'ChatStreamStatusPreviewEvent',
    CHAT_STREAM_COMMAND_ERROR: 'chat_stream_command_error',
    CHAT_TOKEN_COUNT_RESULT: 'chat_token_count_result',
    CHAT_TOKEN_COUNT_ERROR: 'chat_token_count_error',
    COMMAND_ACCEPTED: 'command_accepted',
    INVALID_REQUEST: 'invalid_request',
    FORBIDDEN: 'forbidden',
    NOT_FOUND: 'not_found',
    CONFLICT: 'conflict',
    SERVER_ERROR: 'server_error',
    INVALID_RESOURCE_INTEREST: 'invalid_resource_interest',
    RESOURCE_INTERESTS_APPLIED: 'resource_interests_applied',
    UNKNOWN_MESSAGE: 'unknown_message',
    OPENAI_API_KEY_QUOTA_UPDATED: 'openai_api_key_quota_updated',
    MODEL_TEST_STREAM_EVENT: 'ModelTestStreamEvent',
    AGENT_TURN_STARTED: 'AgentTurnStartedEvent',
    AGENT_ITEM_STARTED: 'AgentItemStartedEvent',
    AGENT_ITEM_DELTA: 'AgentItemDeltaEvent',
    AGENT_ITEM_COMPLETED: 'AgentItemCompletedEvent',
    TOOL_CALL_CREATED: 'ToolCallCreatedEvent',
    TOOL_CALL_STARTED: 'ToolCallStartedEvent',
    TOOL_CALL_LIVE_UPDATED: 'ToolCallLiveUpdatedEvent',
    TOOL_CALL_COMPLETED: 'ToolCallCompletedEvent',
    AGENT_TURN_COMPLETED: 'AgentTurnCompletedEvent',
    AGENT_TURN_ERROR: 'AgentTurnErrorEvent',
    AGENT_TODO_UPDATED: 'AgentTodoUpdatedEvent',
    AGENT_PLAN_UPDATED: 'AgentPlanUpdatedEvent',
    AGENT_MODE_CHANGED: 'AgentModeChangedEvent',
    AGENT_SUBAGENT_SPAWNED: 'SubagentSpawnedEvent',
    AGENT_SUBAGENT_RUNNING: 'SubagentRunningEvent',
    AGENT_SUBAGENT_COMPLETED: 'SubagentCompletedEvent',
    AGENT_SUBAGENT_MAX_ITERATIONS: 'SubagentMaxIterationsEvent',
    AGENT_SUBAGENT_ERROR: 'SubagentErrorEvent',
    AGENT_SUBAGENT_ABANDONED: 'SubagentAbandonedEvent',
    AGENT_SUBAGENT_CANCELLED: 'SubagentCancelledEvent',
    ERROR_EVENT: 'ErrorEvent',
    FILE_SYSTEM_CHANGED: 'FileSystemChangedEvent',
    MCP_NOTIFICATION: 'MCPNotificationEvent',
    MCP_TOOLS_LIST_CHANGED: 'MCPToolsListChangedEvent',
    MCP_RESOURCES_LIST_CHANGED: 'MCPResourcesListChangedEvent',
    MCP_PROMPTS_LIST_CHANGED: 'MCPPromptsListChangedEvent',
    MCP_SERVER_STARTED: 'MCPServerStartedEvent',
    MCP_SERVER_ADDED: 'MCPServerAddedEvent',
    MCP_SERVER_REMOVED: 'MCPServerRemovedEvent',
    MCP_SERVER_CONNECTED: 'MCPServerConnectedEvent',
    MCP_SERVER_DISCONNECTED: 'MCPServerDisconnectedEvent',
    MCP_TOOL_INVOKED: 'MCPToolInvokedEvent',
    KNOWLEDGE_PROMPT_STATE_CHANGED: 'KnowledgePromptStateChangedEvent',
    PTY_CONNECTED: 'pty_connected',
    PTY_OUTPUT: 'pty_output',
    PTY_EXITED: 'pty_exited',
    PTY_DISCONNECTED: 'pty_disconnected',
    PTY_ERROR: 'pty_error',
    PTY_BUSY: 'pty_busy',
    LOG_BATCH: 'log_batch',
    LOG_STREAM_SUBSCRIBED: 'log_stream_subscribed',
    LOG_STREAM_UNSUBSCRIBED: 'log_stream_unsubscribed',
    LOG_STREAM_RECONFIGURED: 'log_stream_reconfigured',
    LOG_STREAM_CLOSED: 'log_stream_closed',
    LOG_STREAM_ERROR: 'log_stream_error',
    WALLPAPER_CHANGED: 'WallpaperChangedEvent',
    NOTIFICATION_CREATED: 'NotificationCreatedEvent',
    NOTIFICATION_DELETED: 'NotificationDeletedEvent',
    NOTIFICATIONS_CLEARED: 'NotificationsClearedEvent',
    NOTIFICATIONS_MARKED_READ: 'NotificationsMarkedReadEvent',
    SNAPSHOT_RESPONSE: 'snapshot_response',
    SNAPSHOT_ERROR: 'snapshot_error',
    PING: 'ping',
    LATENCY_PROBE_RESULT: 'latency_probe_result',
    OPENAI_AUDIO_TRANSCRIPTION_STARTED: 'openai_audio_transcription_started',
    OPENAI_AUDIO_TRANSCRIPTION_COMPLETED: 'openai_audio_transcription_completed',
    OPENAI_AUDIO_TRANSCRIPTION_CANCELLED: 'openai_audio_transcription_cancelled',
    OPENAI_AUDIO_TRANSCRIPTION_ERROR: 'openai_audio_transcription_error',
    OPENAI_AUDIO_SPEECH_STARTED: 'openai_audio_speech_started',
    OPENAI_AUDIO_SPEECH_CHUNK: 'openai_audio_speech_chunk',
    OPENAI_AUDIO_SPEECH_COMPLETED: 'openai_audio_speech_completed',
    OPENAI_AUDIO_SPEECH_CANCELLED: 'openai_audio_speech_cancelled',
    OPENAI_AUDIO_SPEECH_ERROR: 'openai_audio_speech_error',
    OPENAI_AUDIO_SPEECH_SESSION_STARTED: 'openai_audio_speech_session_started',
    OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_STARTED: 'openai_audio_speech_session_segment_started',
    OPENAI_AUDIO_SPEECH_SESSION_CHUNK: 'openai_audio_speech_session_chunk',
    OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_COMPLETED: 'openai_audio_speech_session_segment_completed',
    OPENAI_AUDIO_SPEECH_SESSION_COMPLETED: 'openai_audio_speech_session_completed',
    OPENAI_AUDIO_SPEECH_SESSION_CANCELLED: 'openai_audio_speech_session_cancelled',
    OPENAI_AUDIO_SPEECH_SESSION_ERROR: 'openai_audio_speech_session_error',
    OPENAI_IMAGES_GENERATION_STARTED: 'openai_images_generation_started',
    OPENAI_IMAGES_GENERATION_STREAM_CHUNK: 'openai_images_generation_stream_chunk',
    OPENAI_IMAGES_GENERATION_COMPLETED: 'openai_images_generation_completed',
    OPENAI_IMAGES_GENERATION_CANCELLED: 'openai_images_generation_cancelled',
    OPENAI_IMAGES_GENERATION_ERROR: 'openai_images_generation_error'
});

const WEBSOCKET_LIFECYCLE_EVENT_TYPES = Object.freeze({
    CONNECTED: 'connected',
    DISCONNECTED: 'disconnected'
});

const EVENT_TO_RESOURCE_MAP: Record<string, readonly string[]> = Object.freeze({
    [WEBSOCKET_EVENT_TYPES.HARDWARE_SNAPSHOT_UPDATED]: [HARDWARE],
    [WEBSOCKET_EVENT_TYPES.METRICS_UPDATED]: [METRICS],
    [WEBSOCKET_EVENT_TYPES.MODEL_DATABASE_CHANGE]: [MODELS, MODELS_LAST_USED],
    [WEBSOCKET_EVENT_TYPES.MODEL_LAST_USED_CHANGED]: [MODELS_LAST_USED],
    [WEBSOCKET_EVENT_TYPES.MODEL_LOADED]: [STREAMS.MODELS_COLLECTION],
    [WEBSOCKET_EVENT_TYPES.SOAI_MAIN_STATE_CHANGED]: [STATUS],
    [WEBSOCKET_EVENT_TYPES.POWER_OPERATION_CHANGED]: [POWER_OPERATIONS],
    [WEBSOCKET_EVENT_TYPES.CIRCUIT_BREAKER_STATE_CHANGED]: [STATUS, PLUGINS, MODELS],
    [WEBSOCKET_EVENT_TYPES.PROCESS_LIST_UPDATED]: [HARDWARE_PROCESSES],
    [WEBSOCKET_EVENT_TYPES.MODEL_PARAMETERS_CHANGED]: [MODELS],
    [WEBSOCKET_EVENT_TYPES.MODEL_PARAMETERS_REQUIRE_RELOAD]: [MODELS],
    [WEBSOCKET_EVENT_TYPES.SYSTEM_RESTART_REQUIRED]: [STATUS],
    [WEBSOCKET_EVENT_TYPES.PROVIDER_STATUS_UPDATED]: [PROVIDERS, STATUS, MODELS, PLUGINS],
    [WEBSOCKET_EVENT_TYPES.PLUGIN_RUNTIME_STATE_CHANGED]: [STREAMS.PLUGINS_COLLECTION, STREAMS.MODELS_COLLECTION],
    [WEBSOCKET_EVENT_TYPES.PLUGIN_INSTALLATION_STATE_CHANGED]: [PLUGINS, MODELS],
    [WEBSOCKET_EVENT_TYPES.INSTALLED_PLUGINS_CHANGED]: [PLUGINS, CAPS, MODELS],
    [WEBSOCKET_EVENT_TYPES.PLUGIN_LOADED]: [PLUGINS, MODELS],
    [WEBSOCKET_EVENT_TYPES.PLUGIN_UNLOADED]: [PLUGINS, MODELS],
    [WEBSOCKET_EVENT_TYPES.PLUGIN_PURGED]: [PLUGINS, MODELS, PLUGINS_LAST_USED],
    [WEBSOCKET_EVENT_TYPES.PLUGIN_LAST_USED_CHANGED]: [PLUGINS_LAST_USED],
    [WEBSOCKET_EVENT_TYPES.ROUTING_CONFIG_CHANGED]: [ROUTING, VIRTUAL, MODELS],
    [WEBSOCKET_EVENT_TYPES.GPU_CAPABILITIES_CHANGED]: [HARDWARE_GPU_CAPABILITIES],
    [WEBSOCKET_EVENT_TYPES.GPU_SAVED_SETTINGS_CHANGED]: [HARDWARE_GPU_SLOTS],
    [WEBSOCKET_EVENT_TYPES.GPU_ACTIVE_SLOT_CHANGED]: [HARDWARE_GPU_SLOTS],
    [WEBSOCKET_EVENT_TYPES.GPU_BOOT_PREFERENCE_CHANGED]: [HARDWARE_GPU_SLOTS],
    [WEBSOCKET_EVENT_TYPES.GPU_STARTUP_WARNING]: [HARDWARE_GPU_SLOTS],
    [WEBSOCKET_EVENT_TYPES.SOAIBENCH_RUN_UPDATED]: [HARDWARE_GPU_SOAIBENCH_RUNS],
    [WEBSOCKET_EVENT_TYPES.FILE_SYSTEM_CHANGED]: ['file_explorer.list'],
    [WEBSOCKET_EVENT_TYPES.PROMPT_LIST_UPDATED]: [PROMPTS],
    [WEBSOCKET_EVENT_TYPES.WALLPAPER_CHANGED]: ['webui.wallpaper.status'],
    [WEBSOCKET_EVENT_TYPES.NOTIFICATION_CREATED]: [WEBUI_NOTIFICATIONS],
    [WEBSOCKET_EVENT_TYPES.NOTIFICATION_DELETED]: [WEBUI_NOTIFICATIONS],
    [WEBSOCKET_EVENT_TYPES.NOTIFICATIONS_CLEARED]: [WEBUI_NOTIFICATIONS],
    [WEBSOCKET_EVENT_TYPES.NOTIFICATIONS_MARKED_READ]: [WEBUI_NOTIFICATIONS],
    [WEBSOCKET_EVENT_TYPES.CONVERSATION_ATTENTION_CHANGED]: [WEBUI_CHAT_ATTENTION],
    [WEBSOCKET_EVENT_TYPES.CONVERSATION_DELETED]: [WEBUI_CHAT_ATTENTION],
    [WEBSOCKET_EVENT_TYPES.MESSAGE_SAVED]: [WEBUI_CHAT_ATTENTION],
    [WEBSOCKET_EVENT_TYPES.CHAT_STREAM_ACTIVITY_CHANGED]: [WEBUI_CHAT_ACTIVITY]
});

const WEBSOCKET_UPDATED_RESOURCE_NAMES: readonly string[] = Object.freeze(Array.from(new Set(Object.values(EVENT_TO_RESOURCE_MAP).flat())));

const getResourcesForEventType = (eventType: string): readonly string[] => {
    const resources = EVENT_TO_RESOURCE_MAP[eventType];
    if (resources) {
        return resources;
    }
    return [];
};

const KNOWN_EVENT_TYPES_SET: ReadonlySet<string> = Object.freeze(new Set(Object.values(WEBSOCKET_EVENT_TYPES)));

const WEBSOCKET_TASK_EVENT_TYPES: ReadonlySet<string> = new Set([WEBSOCKET_EVENT_TYPES.TASK_CREATED, WEBSOCKET_EVENT_TYPES.TASK_STATUS_CHANGED, WEBSOCKET_EVENT_TYPES.TASK_PROGRESS, WEBSOCKET_EVENT_TYPES.TASK_COMPLETE]);

const WEBSOCKET_PROTOCOL_ERROR_EVENT_TYPES: ReadonlySet<string> = new Set([WEBSOCKET_EVENT_TYPES.INVALID_REQUEST, WEBSOCKET_EVENT_TYPES.FORBIDDEN, WEBSOCKET_EVENT_TYPES.NOT_FOUND, WEBSOCKET_EVENT_TYPES.CONFLICT, WEBSOCKET_EVENT_TYPES.SERVER_ERROR, WEBSOCKET_EVENT_TYPES.UNKNOWN_MESSAGE, WEBSOCKET_EVENT_TYPES.INVALID_RESOURCE_INTEREST]);

const isKnownEventType = (eventType: string): boolean => KNOWN_EVENT_TYPES_SET.has(eventType);

const isTaskWebSocketEventType = (eventType: string): boolean => WEBSOCKET_TASK_EVENT_TYPES.has(eventType);

const isWebSocketProtocolErrorEventType = (eventType: string): boolean => WEBSOCKET_PROTOCOL_ERROR_EVENT_TYPES.has(eventType);

const isWebSocketUpdatedResource = (resourceName: string): boolean => WEBSOCKET_UPDATED_RESOURCE_NAMES.includes(resourceName);

const WEBSOCKET_MCP_REALTIME_EVENT_TYPES: readonly string[] = Object.freeze([WEBSOCKET_EVENT_TYPES.MCP_NOTIFICATION, WEBSOCKET_EVENT_TYPES.MCP_TOOLS_LIST_CHANGED, WEBSOCKET_EVENT_TYPES.MCP_RESOURCES_LIST_CHANGED, WEBSOCKET_EVENT_TYPES.MCP_PROMPTS_LIST_CHANGED, WEBSOCKET_EVENT_TYPES.MCP_SERVER_STARTED, WEBSOCKET_EVENT_TYPES.MCP_SERVER_ADDED, WEBSOCKET_EVENT_TYPES.MCP_SERVER_REMOVED, WEBSOCKET_EVENT_TYPES.MCP_SERVER_CONNECTED, WEBSOCKET_EVENT_TYPES.MCP_SERVER_DISCONNECTED, WEBSOCKET_EVENT_TYPES.MCP_TOOL_INVOKED]);

const WEBSOCKET_PTY_EVENT_TYPES: readonly string[] = Object.freeze([WEBSOCKET_EVENT_TYPES.PTY_CONNECTED, WEBSOCKET_EVENT_TYPES.PTY_OUTPUT, WEBSOCKET_EVENT_TYPES.PTY_EXITED, WEBSOCKET_EVENT_TYPES.PTY_DISCONNECTED, WEBSOCKET_EVENT_TYPES.PTY_ERROR, WEBSOCKET_EVENT_TYPES.PTY_BUSY]);

const WEBSOCKET_LOG_STREAM_EVENT_TYPES: readonly string[] = Object.freeze([WEBSOCKET_EVENT_TYPES.LOG_BATCH, WEBSOCKET_EVENT_TYPES.LOG_STREAM_SUBSCRIBED, WEBSOCKET_EVENT_TYPES.LOG_STREAM_CLOSED, WEBSOCKET_EVENT_TYPES.LOG_STREAM_UNSUBSCRIBED, WEBSOCKET_EVENT_TYPES.LOG_STREAM_RECONFIGURED, WEBSOCKET_EVENT_TYPES.LOG_STREAM_ERROR]);

type WebSocketMessageTypes = typeof WEBSOCKET_MESSAGE_TYPES;
type WebSocketEventTypes = typeof WEBSOCKET_EVENT_TYPES;

export { EVENT_TO_RESOURCE_MAP, WEBSOCKET_EVENT_TYPES, WEBSOCKET_LIFECYCLE_EVENT_TYPES, WEBSOCKET_LOG_STREAM_EVENT_TYPES, WEBSOCKET_MCP_REALTIME_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES, WEBSOCKET_PTY_EVENT_TYPES, getResourcesForEventType, isKnownEventType, isTaskWebSocketEventType, isWebSocketProtocolErrorEventType, isWebSocketUpdatedResource };
export type { WebSocketEventTypes, WebSocketMessageTypes };
