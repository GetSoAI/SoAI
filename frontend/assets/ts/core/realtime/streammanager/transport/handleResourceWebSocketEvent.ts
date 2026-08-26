/* SoAI - Shared realtime handle resource WebSocket event [frontend/assets/ts/core/realtime/streammanager/transport/handleResourceWebSocketEvent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { HARDWARE, HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES, METRICS, MODELS_LAST_USED, PLUGINS_LAST_USED, POWER_OPERATIONS, PROMPTS, ROUTING, VIRTUAL, WEBUI_CHAT_ACTIVITY } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceEntry, ResourceUpdateOutcome } from '@core/realtime/streammanager/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isArray, isObject } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';
import { hasResourceDemand } from '@core/realtime/streammanager/resources/resourceActivationPolicy.ts';

interface HandleResourceWebSocketEventOptions {
    module: string;
    eventType: string;
    payload: JsonObject;
    resourcesForEventType: readonly string[];
    getResource: (name: string) => ResourceEntry | null;
    updateResource: (name: string, payload: JsonValue | null, updateType: string, raw: JsonValue | null) => ResourceUpdateOutcome;
    notifyResource?: (name: string, updateType: string, raw: JsonValue | null) => void;
    startResource: (name: string, options: { forceRefresh: boolean }) => Promise<JsonValue | null>;
}

interface RecoverResourceWebSocketEventOptions {
    module: string;
    raw: JsonValue;
    resourcesForEventType: readonly string[];
    handledResources: ReadonlySet<string>;
    getResource: HandleResourceWebSocketEventOptions['getResource'];
    notifyResource?: HandleResourceWebSocketEventOptions['notifyResource'];
    startResource: HandleResourceWebSocketEventOptions['startResource'];
}

const isGpuSlotEventType = (eventType: string): boolean => eventType === WEBSOCKET_EVENT_TYPES.GPU_SAVED_SETTINGS_CHANGED || eventType === WEBSOCKET_EVENT_TYPES.GPU_ACTIVE_SLOT_CHANGED || eventType === WEBSOCKET_EVENT_TYPES.GPU_BOOT_PREFERENCE_CHANGED || eventType === WEBSOCKET_EVENT_TYPES.GPU_STARTUP_WARNING;

const copyJsonFieldIfPresent = (target: JsonObject, source: JsonObject, fieldName: string): void => {
    if (!hasOwn(source, fieldName)) return;
    const value = source[fieldName];
    if (value !== undefined) {
        target[fieldName] = value;
    }
};

const applyPushedResource = (options: { name: string; payload: JsonValue | null; raw: JsonObject; updatedResources: Set<string>; updateResource: HandleResourceWebSocketEventOptions['updateResource']; marksEventHandled?: boolean }): void => {
    const outcome = options.updateResource(options.name, options.payload, 'websocket-push', options.raw);
    if (outcome !== 'rejected' && options.marksEventHandled !== false) {
        options.updatedResources.add(options.name);
    }
};

const recoverUnappliedResources = (options: RecoverResourceWebSocketEventOptions): void => {
    for (const resourceName of options.resourcesForEventType) {
        if (options.handledResources.has(resourceName)) continue;
        const resource = options.getResource(resourceName);
        if (!resource || resource.reconciler.snapshot.maintenance || resource.reconciler.snapshot.authoritativeReason === 'optional-resource-unavailable') continue;
        if (!hasResourceDemand(resource)) continue;
        resource.reconciler.invalidate('websocket-recovery');
        options.notifyResource?.(resourceName, 'websocket-recovery', options.raw);
        const hasRecoveryTransport = resource.config.websocketOnly || resource.config.fetch !== null;
        if (!hasRecoveryTransport) {
            errorHandler.warn(options.module, `Resource cannot recover from WebSocket event: ${resourceName}`);
            continue;
        }
        options.startResource(resourceName, { forceRefresh: false }).catch((error) => {
            if (error instanceof Error && error.message !== 'Maintenance' && !isLifecycleCancellationError(error)) {
                errorHandler.warn(options.module, `Resource start failed for ${resourceName}`, error);
            }
        });
    }
};

const recoverMalformedResourceWebSocketEvent = (options: Omit<RecoverResourceWebSocketEventOptions, 'handledResources'>): void => {
    recoverUnappliedResources({ ...options, handledResources: new Set<string>() });
};

const handleResourceWebSocketEvent = (options: HandleResourceWebSocketEventOptions): void => {
    if (!isObject(options)) {
        throw new Error('handleResourceWebSocketEvent requires options');
    }
    const { module, eventType, payload, resourcesForEventType, getResource, updateResource, notifyResource, startResource } = options;

    const updatedResources = new Set<string>();

    if (isArray(payload['prompts'])) {
        applyPushedResource({ name: PROMPTS, payload: payload['prompts'], raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.HARDWARE_SNAPSHOT_UPDATED && isObject(payload['snapshot'])) {
        applyPushedResource({ name: HARDWARE, payload: payload['snapshot'], raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.METRICS_UPDATED && isObject(payload['metrics'])) {
        applyPushedResource({ name: METRICS, payload: payload['metrics'], raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.POWER_OPERATION_CHANGED) {
        applyPushedResource({ name: POWER_OPERATIONS, payload, raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.PROCESS_LIST_UPDATED && isArray(payload['processes'])) {
        applyPushedResource({ name: HARDWARE_PROCESSES, payload: payload['processes'], raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.ROUTING_CONFIG_CHANGED) {
        const routingUpdate: JsonObject = {};
        copyJsonFieldIfPresent(routingUpdate, payload, 'trace_id');
        copyJsonFieldIfPresent(routingUpdate, payload, 'event_id');
        copyJsonFieldIfPresent(routingUpdate, payload, 'timestamp');
        copyJsonFieldIfPresent(routingUpdate, payload, 'virtual_models');
        copyJsonFieldIfPresent(routingUpdate, payload, 'failovers');
        copyJsonFieldIfPresent(routingUpdate, payload, 'routing_config');
        if (Object.keys(routingUpdate).length) {
            applyPushedResource({ name: ROUTING, payload: routingUpdate, raw: payload, updatedResources, updateResource });
        }
        if (isArray(payload['virtual_models'])) {
            applyPushedResource({ name: VIRTUAL, payload: payload['virtual_models'], raw: payload, updatedResources, updateResource });
        }
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.GPU_CAPABILITIES_CHANGED && isObject(payload['capabilities'])) {
        applyPushedResource({ name: HARDWARE_GPU_CAPABILITIES, payload: payload['capabilities'], raw: payload, updatedResources, updateResource });
    }

    if (isGpuSlotEventType(eventType)) {
        const hasSnapshotPayload = isObject(payload['devices']);
        const slotResource = getResource(HARDWARE_GPU_SLOTS);
        if (hasSnapshotPayload || slotResource?.value != null) {
            applyPushedResource({ name: HARDWARE_GPU_SLOTS, payload, raw: payload, updatedResources, updateResource, marksEventHandled: hasSnapshotPayload });
        }
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.SOAIBENCH_RUN_UPDATED) {
        applyPushedResource({ name: HARDWARE_GPU_SOAIBENCH_RUNS, payload, raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.CHAT_STREAM_ACTIVITY_CHANGED) {
        applyPushedResource({ name: WEBUI_CHAT_ACTIVITY, payload, raw: payload, updatedResources, updateResource });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.MODEL_LAST_USED_CHANGED) {
        applyPushedResource({
            name: MODELS_LAST_USED,
            payload: {
                'universal_id': payload['universal_id'] ?? null,
                'last_used_at_ms': payload['last_used_at_ms'] ?? null,
                revision: payload['revision'] ?? null
            },
            raw: payload,
            updatedResources,
            updateResource
        });
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.PLUGIN_LAST_USED_CHANGED) {
        applyPushedResource({
            name: PLUGINS_LAST_USED,
            payload: {
                'plugin_name': payload['plugin_name'] ?? null,
                'last_used_at_ms': payload['last_used_at_ms'] ?? null,
                revision: payload['revision'] ?? null
            },
            raw: payload,
            updatedResources,
            updateResource
        });
    }

    recoverUnappliedResources({ module, raw: payload, resourcesForEventType, handledResources: updatedResources, getResource, notifyResource, startResource });
};

export { handleResourceWebSocketEvent, recoverMalformedResourceWebSocketEvent };
