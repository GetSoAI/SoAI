/* SoAI - System metrics V1 runtime block contracts [frontend/assets/ts/core/realtime/streammanager/resources/systemMetricsRuntimeContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { decodeSystemMetricsTimings } from '@core/realtime/streammanager/resources/systemMetricsTimingContracts.ts';
import { assignOptionalSection, decodeFiniteNumberFields, decodeFiniteNumberMap, decodeNestedFiniteNumberMap, decodeStringFields, optionalMetricsObject } from '@core/realtime/streammanager/resources/systemMetricsValueDecoding.ts';

const decodeUniqueClients = (source: JsonObject, label: string): JsonObject | undefined => {
    const uniqueClients = optionalMetricsObject(source, 'unique_clients', label);
    return uniqueClients ? decodeFiniteNumberFields(uniqueClients, { 'cardinality_1h': 'cardinality1h' }, `${label}.unique_clients`) : undefined;
};

const decodeApiMetrics = (root: JsonObject): JsonObject | undefined => {
    const api = optionalMetricsObject(root, 'api', 'system.metrics');
    if (!api) return undefined;
    const decoded: JsonObject = {};
    const openai = optionalMetricsObject(api, 'openai', 'system.metrics.api');
    if (openai) {
        const decodedOpenai = decodeFiniteNumberFields(
            openai,
            {
                'requests_total_chat_completions': 'requestsTotalChatCompletions',
                'requests_total_text_completions': 'requestsTotalTextCompletions',
                'requests_total_embedding': 'requestsTotalEmbedding',
                'requests_total_image': 'requestsTotalImage',
                'requests_total_tts': 'requestsTotalTts',
                'requests_total_responses': 'requestsTotalResponses',
                'requests_failed': 'requestsFailed',
                'list_models_requests': 'listModelsRequests',
                'get_model_details_requests': 'getModelDetailsRequests'
            },
            'system.metrics.api.openai'
        );
        const requestsByModel = optionalMetricsObject(openai, 'requests_by_model', 'system.metrics.api.openai');
        const authFailures = optionalMetricsObject(openai, 'auth_failures', 'system.metrics.api.openai');
        if (requestsByModel) decodedOpenai['requestsByModel'] = decodeFiniteNumberMap(requestsByModel, 'system.metrics.api.openai.requests_by_model');
        if (authFailures) decodedOpenai['authFailures'] = decodeFiniteNumberMap(authFailures, 'system.metrics.api.openai.auth_failures');
        assignOptionalSection(decodedOpenai, 'uniqueClients', decodeUniqueClients(openai, 'system.metrics.api.openai'));
        assignOptionalSection(decodedOpenai, 'timings', decodeSystemMetricsTimings(openai, 'system.metrics.api.openai', { 'request_latency_ms': 'requestLatencyMs' }));
        decoded['openai'] = decodedOpenai;
    }
    const system = optionalMetricsObject(api, 'system', 'system.metrics.api');
    if (system) {
        const decodedSystem = decodeFiniteNumberFields(system, { 'status_stream_connections': 'statusStreamConnections', 'list_models_requests': 'listModelsRequests', 'direct_requests_submitted': 'directRequestsSubmitted' }, 'system.metrics.api.system');
        assignOptionalSection(decodedSystem, 'uniqueClients', decodeUniqueClients(system, 'system.metrics.api.system'));
        decoded['system'] = decodedSystem;
    }
    const unknown = optionalMetricsObject(api, 'unknown', 'system.metrics.api');
    if (unknown) {
        const decodedUnknown: JsonObject = {};
        assignOptionalSection(decodedUnknown, 'uniqueClients', decodeUniqueClients(unknown, 'system.metrics.api.unknown'));
        decoded['unknown'] = decodedUnknown;
    }
    const webui = optionalMetricsObject(api, 'webui', 'system.metrics.api');
    if (webui) decoded['webui'] = decodeFiniteNumberFields(webui, { 'conversations_created': 'conversationsCreated', 'conversation_messages_updated': 'conversationMessagesUpdated', 'conversation_settings_updated': 'conversationSettingsUpdated', 'conversations_deleted': 'conversationsDeleted', 'chat_messages_sent': 'chatMessagesSent' }, 'system.metrics.api.webui');
    const tasks = optionalMetricsObject(api, 'tasks', 'system.metrics.api');
    if (tasks) decoded['tasks'] = decodeFiniteNumberFields(tasks, { 'list_active': 'listActive', list: 'list', 'stream_reconnect': 'streamReconnect', get: 'get', cancel: 'cancel', 'software_update_started': 'softwareUpdateStarted', 'software_update_completed': 'softwareUpdateCompleted', 'software_update_failed': 'softwareUpdateFailed' }, 'system.metrics.api.tasks');
    return decoded;
};

const decodeGlobalMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'global', 'system.metrics');
    if (!source) return undefined;
    const decoded = decodeFiniteNumberFields(source, { 'start_time_ms': 'startTimeMs', 'restarts_triggered': 'restartsTriggered', 'updates_triggered': 'updatesTriggered' }, 'system.metrics.global');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.global', { 'startup_duration_ms': 'startupDurationMs' }));
    return decoded;
};

const decodeEventBusMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'event_bus', 'system.metrics');
    if (!source) return undefined;
    const decoded = decodeFiniteNumberFields(source, { 'events_dropped': 'eventsDropped' }, 'system.metrics.event_bus');
    const callbacks = optionalMetricsObject(source, 'callbacks', 'system.metrics.event_bus');
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.event_bus');
    if (callbacks) decoded['callbacks'] = decodeFiniteNumberFields(callbacks, { 'refused_cancellation': 'refusedCancellation' }, 'system.metrics.event_bus.callbacks');
    if (gauges) decoded['gauges'] = decodeFiniteNumberFields(gauges, { 'queue_depth': 'queueDepth', 'dispatched_callback_count': 'dispatchedCallbackCount' }, 'system.metrics.event_bus.gauges');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.event_bus', { 'queue_time_ms': 'queueTimeMs', 'dispatch_time_ms': 'dispatchTimeMs' }));
    return decoded;
};

const decodeStreamingMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'streaming', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const sections: ReadonlyArray<readonly [string, string, Readonly<Record<string, string>>]> = [
        ['backpressure', 'backpressure', { 'dropped_events': 'droppedEvents' }],
        ['channel', 'channel', { 'eviction_terminal_count': 'evictionTerminalCount' }],
        ['delivery', 'delivery', { 'timeout_count': 'timeoutCount', 'shutdown_count': 'shutdownCount', 'failed_count': 'failedCount', 'terminal_failed_count': 'terminalFailedCount' }],
        ['listener', 'listener', { 'stale_removed_count': 'staleRemovedCount' }],
        ['chunks', 'chunks', { 'coalesced_count': 'coalescedCount' }],
        ['queue', 'queue', { 'double_finalization_count': 'doubleFinalizationCount' }]
    ];
    for (const [wireName, domainName, fields] of sections) {
        const section = optionalMetricsObject(source, wireName, 'system.metrics.streaming');
        if (section) decoded[domainName] = decodeFiniteNumberFields(section, fields, `system.metrics.streaming.${wireName}`);
    }
    return decoded;
};

const decodeWebsocketMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'websocket', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const logStream = optionalMetricsObject(source, 'log_stream', 'system.metrics.websocket');
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.websocket');
    const drops = logStream ? optionalMetricsObject(logStream, 'drops', 'system.metrics.websocket.log_stream') : undefined;
    const queueDepth = gauges ? optionalMetricsObject(gauges, 'queue_depth', 'system.metrics.websocket.gauges') : undefined;
    if (logStream) decoded['logStream'] = drops ? { drops: decodeFiniteNumberMap(drops, 'system.metrics.websocket.log_stream.drops') } : {};
    if (gauges) decoded['gauges'] = queueDepth ? { queueDepth: decodeFiniteNumberMap(queueDepth, 'system.metrics.websocket.gauges.queue_depth') } : {};
    return decoded;
};

const decodeModelManagerMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'model_manager', 'system.metrics');
    if (!source) return undefined;
    const decoded = decodeFiniteNumberFields(source, { 'discoveries_run': 'discoveriesRun', 'models_updated': 'modelsUpdated', 'models_removed': 'modelsRemoved', 'param_updates_processed': 'parameterUpdatesProcessed', 'param_deletes_processed': 'parameterDeletesProcessed' }, 'system.metrics.model_manager');
    const discoveriesFailed = optionalMetricsObject(source, 'discoveries_failed', 'system.metrics.model_manager');
    if (discoveriesFailed) decoded['discoveriesFailed'] = decodeFiniteNumberMap(discoveriesFailed, 'system.metrics.model_manager.discoveries_failed');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.model_manager', { 'discovery_duration_ms': 'discoveryDurationMs' }));
    return decoded;
};

const decodeStateMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'state', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const eventsEmitted = optionalMetricsObject(source, 'events_emitted', 'system.metrics.state');
    const statusChanges = optionalMetricsObject(source, 'plugin_status_changes', 'system.metrics.state');
    const inactivityActions = optionalMetricsObject(source, 'inactivity_actions_triggered', 'system.metrics.state');
    if (eventsEmitted) decoded['eventsEmitted'] = decodeFiniteNumberMap(eventsEmitted, 'system.metrics.state.events_emitted');
    if (statusChanges) decoded['pluginStatusChanges'] = decodeNestedFiniteNumberMap(statusChanges, 'system.metrics.state.plugin_status_changes');
    if (inactivityActions) decoded['inactivityActionsTriggered'] = decodeFiniteNumberMap(inactivityActions, 'system.metrics.state.inactivity_actions_triggered');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.state', { 'write_lock_duration_ms': 'writeLockDurationMs', 'read_lock_duration_ms': 'readLockDurationMs' }));
    return decoded;
};

const decodeDatabaseMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'database', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.database');
    if (gauges) decoded['gauges'] = decodeFiniteNumberFields(gauges, { 'db_read_kbps': 'databaseReadKbps', 'db_write_kbps': 'databaseWriteKbps', 'write_queue_depth': 'writeQueueDepth', 'process_read_kbps': 'processReadKbps', 'process_write_kbps': 'processWriteKbps', 'db_file_write_kbps': 'databaseFileWriteKbps', 'db_file_truncate_kbps': 'databaseFileTruncateKbps', 'db_file_size_kb': 'databaseFileSizeKb' }, 'system.metrics.database.gauges');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.database', { 'write_op_duration_ms': 'writeOperationDurationMs' }));
    return decoded;
};

const decodeDownloadSpeedMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'download_speed', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.download_speed');
    const counters = optionalMetricsObject(source, 'counters', 'system.metrics.download_speed');
    if (gauges) decoded['gauges'] = { ...decodeFiniteNumberFields(gauges, { 'current_median_bps': 'currentMedianBps', 'sample_count': 'sampleCount', 'last_download_bps': 'lastDownloadBps', 'last_updated_ms': 'lastUpdatedMs' }, 'system.metrics.download_speed.gauges'), ...decodeStringFields(gauges, { source: 'source' }, 'system.metrics.download_speed.gauges') };
    if (counters) decoded['counters'] = decodeFiniteNumberFields(counters, { 'total_downloads_tracked': 'totalDownloadsTracked' }, 'system.metrics.download_speed.counters');
    return decoded;
};

const decodeGenesisMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'genesis', 'system.metrics');
    return source ? decodeFiniteNumberFields(source, { 'uptime_ms': 'uptimeMs', 'current_session_ms': 'currentSessionMs', 'requests_total': 'requestsTotal', 'tokens_total': 'tokensTotal', 'first_startup_ts_ms': 'firstStartupTimestampMs', 'current_session_start_ts_ms': 'currentSessionStartTimestampMs' }, 'system.metrics.genesis') : undefined;
};

export { decodeApiMetrics, decodeDatabaseMetrics, decodeDownloadSpeedMetrics, decodeEventBusMetrics, decodeGenesisMetrics, decodeGlobalMetrics, decodeModelManagerMetrics, decodeStateMetrics, decodeStreamingMetrics, decodeWebsocketMetrics };
