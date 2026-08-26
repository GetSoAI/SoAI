/* SoAI - System metrics V1 orchestration block contracts [frontend/assets/ts/core/realtime/streammanager/resources/systemMetricsOrchestrationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { decodeSystemMetricsTimings } from '@core/realtime/streammanager/resources/systemMetricsTimingContracts.ts';
import { assignOptionalSection, decodeFiniteNumberFields, decodeFiniteNumberMap, optionalMetricsObject } from '@core/realtime/streammanager/resources/systemMetricsValueDecoding.ts';

const decodeDirectorMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'director', 'system.metrics');
    if (!source) return undefined;
    const decoded = decodeFiniteNumberFields(source, { 'evictions_triggered': 'evictionsTriggered' }, 'system.metrics.director');
    const requests = optionalMetricsObject(source, 'requests', 'system.metrics.director');
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.director');
    const modelLoads = optionalMetricsObject(source, 'model_loads', 'system.metrics.director');
    if (requests) decoded['requests'] = decodeFiniteNumberFields(requests, { total: 'total', queued: 'queued', completed: 'completed', failed: 'failed', cancelled: 'cancelled', 'fast_path': 'fastPath', 'express_path': 'expressPath', deduplicated: 'deduplicated' }, 'system.metrics.director.requests');
    if (gauges) {
        const decodedGauges = decodeFiniteNumberFields(gauges, { 'queue_size': 'queueSize', 'request_latency_ms': 'requestLatencyMs', 'pending_loads': 'pendingLoads' }, 'system.metrics.director.gauges');
        const gaugeMaps: ReadonlyArray<readonly [string, string]> = [
            ['plugin_health', 'pluginHealth'],
            ['plugin_concurrency_limit', 'pluginConcurrencyLimit'],
            ['plugin_concurrency_active', 'pluginConcurrencyActive'],
            ['plugin_concurrency_waiters', 'pluginConcurrencyWaiters']
        ];
        for (const [wireName, domainName] of gaugeMaps) {
            const map = optionalMetricsObject(gauges, wireName, 'system.metrics.director.gauges');
            if (map) decodedGauges[domainName] = decodeFiniteNumberMap(map, `system.metrics.director.gauges.${wireName}`);
        }
        decoded['gauges'] = decodedGauges;
    }
    if (modelLoads) decoded['modelLoads'] = decodeFiniteNumberFields(modelLoads, { successful: 'successful', failed: 'failed' }, 'system.metrics.director.model_loads');
    const dynamicMaps: ReadonlyArray<readonly [string, string]> = [
        ['health_check_recoveries', 'healthCheckRecoveries'],
        ['health_ping_failures', 'healthPingFailures'],
        ['requests_by_model', 'requestsByModel'],
        ['requests_by_virtual_model', 'requestsByVirtualModel'],
        ['failovers_applied', 'failoversApplied'],
        ['persistent_plugin_request_timeouts', 'persistentPluginRequestTimeouts']
    ];
    for (const [wireName, domainName] of dynamicMaps) {
        const map = optionalMetricsObject(source, wireName, 'system.metrics.director');
        if (map) decoded[domainName] = decodeFiniteNumberMap(map, `system.metrics.director.${wireName}`);
    }
    assignOptionalSection(
        decoded,
        'timings',
        decodeSystemMetricsTimings(source, 'system.metrics.director', {
            'model_load_latency_ms': 'modelLoadLatencyMs',
            'request_wait_time_ms': 'requestWaitTimeMs',
            'state_lock_wait_ms': 'stateLockWaitMs',
            'dedup_lock_wait_ms': 'deduplicationLockWaitMs',
            'routing_config_lock_wait_ms': 'routingConfigurationLockWaitMs',
            'active_inferences_lock_wait_ms': 'activeInferencesLockWaitMs'
        })
    );
    return decoded;
};

const decodeOrchestratorMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'orchestrator', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const promptQueuing = optionalMetricsObject(source, 'prompt_queuing', 'system.metrics.orchestrator');
    const queue = optionalMetricsObject(source, 'queue', 'system.metrics.orchestrator');
    const invariants = optionalMetricsObject(source, 'invariants', 'system.metrics.orchestrator');
    const execution = optionalMetricsObject(source, 'execution', 'system.metrics.orchestrator');
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.orchestrator');
    if (promptQueuing) decoded['promptQueuing'] = decodeFiniteNumberFields(promptQueuing, { 'slots_held': 'slotsHeld', 'slot_limit': 'slotLimit' }, 'system.metrics.orchestrator.prompt_queuing');
    if (queue) decoded['queue'] = decodeFiniteNumberFields(queue, { 'double_finalization_count': 'doubleFinalizationCount' }, 'system.metrics.orchestrator.queue');
    if (invariants) decoded['invariants'] = decodeFiniteNumberFields(invariants, { 'invariant_violation_count': 'invariantViolationCount' }, 'system.metrics.orchestrator.invariants');
    if (execution) {
        const decodedExecution = decodeFiniteNumberFields(execution, { 'retries_total': 'retriesTotal' }, 'system.metrics.orchestrator.execution');
        const retriesByPlugin = optionalMetricsObject(execution, 'retries_by_plugin', 'system.metrics.orchestrator.execution');
        const retriesByException = optionalMetricsObject(execution, 'retries_by_exception', 'system.metrics.orchestrator.execution');
        if (retriesByPlugin) decodedExecution['retriesByPlugin'] = decodeFiniteNumberMap(retriesByPlugin, 'system.metrics.orchestrator.execution.retries_by_plugin');
        if (retriesByException) decodedExecution['retriesByException'] = decodeFiniteNumberMap(retriesByException, 'system.metrics.orchestrator.execution.retries_by_exception');
        decoded['execution'] = decodedExecution;
    }
    if (gauges) {
        const decodedGauges: JsonObject = {};
        const invariantGauges = optionalMetricsObject(gauges, 'invariants', 'system.metrics.orchestrator.gauges');
        const queueGauges = optionalMetricsObject(gauges, 'queue', 'system.metrics.orchestrator.gauges');
        if (invariantGauges) {
            const decodedInvariants = decodeFiniteNumberFields(invariantGauges, { 'prompt_slot_held_delta': 'promptSlotHeldDelta' }, 'system.metrics.orchestrator.gauges.invariants');
            const pluginActiveDelta = optionalMetricsObject(invariantGauges, 'plugin_active_delta', 'system.metrics.orchestrator.gauges.invariants');
            if (pluginActiveDelta) decodedInvariants['pluginActiveDelta'] = decodeFiniteNumberMap(pluginActiveDelta, 'system.metrics.orchestrator.gauges.invariants.plugin_active_delta');
            decodedGauges['invariants'] = decodedInvariants;
        }
        if (queueGauges) {
            const decodedQueue: JsonObject = {};
            const openCycles = optionalMetricsObject(queueGauges, 'open_cycles', 'system.metrics.orchestrator.gauges.queue');
            if (openCycles) decodedQueue['openCycles'] = decodeFiniteNumberMap(openCycles, 'system.metrics.orchestrator.gauges.queue.open_cycles');
            decodedGauges['queue'] = decodedQueue;
        }
        decoded['gauges'] = decodedGauges;
    }
    return decoded;
};

const decodePluginMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'plugins', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    for (const [pluginName, value] of Object.entries(source)) {
        if (!isJsonObject(value)) throw new TypeError(`system.metrics.plugins.${pluginName} must be an object`);
        const plugin = decodeFiniteNumberFields(value, { 'requests_total': 'requestsTotal', 'requests_failed': 'requestsFailed', 'requests_succeeded': 'requestsSucceeded' }, `system.metrics.plugins.${pluginName}`);
        assignOptionalSection(plugin, 'timings', decodeSystemMetricsTimings(value, `system.metrics.plugins.${pluginName}`, { 'request_latency_ms': 'requestLatencyMs' }));
        decoded[pluginName] = plugin;
    }
    return decoded;
};

const decodeBillingMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'billing', 'system.metrics');
    if (!source) return undefined;
    const decoded = decodeFiniteNumberFields(source, { 'total_tokens_generated': 'totalTokensGenerated' }, 'system.metrics.billing');
    const maps: ReadonlyArray<readonly [string, string]> = [
        ['tokens_by_plugin', 'tokensByPlugin'],
        ['tokens_by_model', 'tokensByModel'],
        ['tokens_by_client', 'tokensByClient']
    ];
    for (const [wireName, domainName] of maps) {
        const map = optionalMetricsObject(source, wireName, 'system.metrics.billing');
        if (map) decoded[domainName] = decodeFiniteNumberMap(map, `system.metrics.billing.${wireName}`);
    }
    return decoded;
};

const decodeUsageEntry = (value: JsonValue, label: string): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError(`${label} must be an object`);
    return decodeFiniteNumberFields(value, { 'text_tokens': 'textTokens', 'audio_input_bytes': 'audioInputBytes', 'audio_input_seconds': 'audioInputSeconds', 'audio_output_bytes': 'audioOutputBytes', 'audio_output_seconds': 'audioOutputSeconds', 'image_input_count': 'imageInputCount', 'image_output_count': 'imageOutputCount' }, label);
};

const decodeUsageMap = (source: JsonObject, wireName: string): JsonObject | undefined => {
    const map = optionalMetricsObject(source, wireName, 'system.metrics.usage');
    if (!map) return undefined;
    const decoded: JsonObject = {};
    for (const [entryName, value] of Object.entries(map)) decoded[entryName] = decodeUsageEntry(value, `system.metrics.usage.${wireName}.${entryName}`);
    return decoded;
};

const decodeUsageMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'usage', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const totals = source['totals'];
    if (totals !== undefined && totals !== null) decoded['totals'] = decodeUsageEntry(totals, 'system.metrics.usage.totals');
    assignOptionalSection(decoded, 'byPlugin', decodeUsageMap(source, 'by_plugin'));
    assignOptionalSection(decoded, 'byModel', decodeUsageMap(source, 'by_model'));
    assignOptionalSection(decoded, 'byClient', decodeUsageMap(source, 'by_client'));
    const compaction = optionalMetricsObject(source, 'compaction', 'system.metrics.usage');
    if (compaction) decoded['compaction'] = decodeFiniteNumberFields(compaction, { 'completed_count': 'completedCount', 'tokens_saved_total': 'tokensSavedTotal' }, 'system.metrics.usage.compaction');
    return decoded;
};

const decodeInactivityMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'inactivity_monitor', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.inactivity_monitor');
    const actions = optionalMetricsObject(source, 'actions_triggered', 'system.metrics.inactivity_monitor');
    if (gauges) decoded['gauges'] = decodeFiniteNumberFields(gauges, { 'last_activity_timestamp': 'lastActivityTimestamp', 'inactive_ms': 'inactiveMs' }, 'system.metrics.inactivity_monitor.gauges');
    if (actions) decoded['actionsTriggered'] = decodeFiniteNumberMap(actions, 'system.metrics.inactivity_monitor.actions_triggered');
    return decoded;
};

export { decodeBillingMetrics, decodeDirectorMetrics, decodeInactivityMetrics, decodeOrchestratorMetrics, decodePluginMetrics, decodeUsageMetrics };
