/* SoAI - Shared realtime default factories [frontend/assets/ts/core/realtime/streammanager/resources/defaultFactories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MODELS_BASE_PATH } from '@core/api/endpoints/models.ts';
import { decodeActivePowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import { decodeSystemMetricsResponse, type SystemMetricsResponse } from '@core/api/contracts/systemMetricsContracts.ts';
import { decodeConversationAttentionResource, type ConversationAttentionResource } from '@core/chat/conversationAttentionSnapshot.ts';
import { decodeChatStreamActivityResource, type ChatStreamActivityResource } from '@core/chat/chatStreamActivitySnapshot.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isCircuitBreakerStateActive, normalizeCircuitBreakerState } from '@core/plugins/circuitBreaker.ts';
import { CAPS, HARDWARE, HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES, LOGS_CORE, METRICS, MODELS, MODELS_LAST_USED, PLUGINS, PLUGINS_LAST_USED, POWER_OPERATIONS, PROMPTS, ROUTING, STATUS, VIRTUAL, WEBUI_CHAT_ACTIVITY, WEBUI_CHAT_ATTENTION, WEBUI_NOTIFICATIONS } from '@core/realtime/streammanager/resources/ids.ts';
import { createLatestUsageResource } from '@core/realtime/streammanager/resources/latestUsageResource.ts';
import { normalizeGpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesResource.ts';
import { normCaps, webSocketResource } from '@core/realtime/streammanager/resources/normalizers.ts';
import { decodeHardwareProcessesResource, decodeHardwareSnapshotResource, decodeLogsResource, decodeModelsResource, decodeNotificationsResource, decodePluginsResource, decodePromptsResource, decodeRoutingConfigResource, decodeVirtualModelsResource } from '@core/realtime/streammanager/resources/resourceDecoders.ts';
import type { HardwareProcessesResource, HardwareSnapshotResource, LogsResource, NotificationsResource, PluginCapabilitiesResource, PluginsResource, PromptsResource, RoutingConfigResource, VirtualModelsResource } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';
import { createSoAIBenchRunsResource } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';
import { normalizeSystemStatusResource } from '@core/realtime/streammanager/resources/systemStatusResource.ts';
import type { ResourceFactory } from '@core/realtime/streammanager/types.ts';
import type { StreamResourceId, StreamResourceValue, SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type DefaultResourceFactories = Partial<{ [ResourceId in StreamResourceId]: ResourceFactory<StreamResourceValue<ResourceId>> }>;

const DEFAULT_RESOURCE_FACTORIES: Readonly<Record<string, ResourceFactory>> & Readonly<DefaultResourceFactories> = Object.freeze({
    [MODELS]: (manager) => ({
        fetch: manager.createApiFetcher(MODELS_BASE_PATH),
        transform: decodeModelsResource
    }),
    [MODELS_LAST_USED]: createLatestUsageResource('universal_id'),
    [PLUGINS]: webSocketResource<PluginsResource>((payload: JsonValue | null) => {
        return decodePluginsResource(payload)
            .map((entry) => {
                const plugin = entry;
                const stateText = String(plugin['state']).toUpperCase();
                const circuitBreaker = isPlainObject(plugin['circuitBreaker']) ? plugin['circuitBreaker'] : null;
                const circuitBreakerState = normalizeCircuitBreakerState(circuitBreaker?.['state']);
                const breakerActive = isCircuitBreakerStateActive(circuitBreakerState, circuitBreaker?.['isOpen']);
                const name = toTrimmedString(plugin['name']);
                return {
                    ...plugin,
                    name,
                    state: breakerActive ? 'QUARANTINED' : stateText,
                    isEnabled: breakerActive ? false : plugin['isEnabled'] === true,
                    circuitBreaker: circuitBreaker
                        ? {
                              ...circuitBreaker,
                              wasEnabled: (circuitBreaker['wasEnabled'] ?? plugin['isEnabled']) === true
                          }
                        : null
                };
            })
            .sort((leftResource, rightResource) => String(leftResource['name'] ?? '').localeCompare(String(rightResource['name'] ?? ''), getLanguageService().getLocale()));
    }),
    [PLUGINS_LAST_USED]: createLatestUsageResource('plugin_name'),
    [CAPS]: webSocketResource<PluginCapabilitiesResource>(normCaps),
    [ROUTING]: webSocketResource<RoutingConfigResource>(decodeRoutingConfigResource),
    [VIRTUAL]: webSocketResource<VirtualModelsResource>(decodeVirtualModelsResource),
    [PROMPTS]: webSocketResource<PromptsResource>(decodePromptsResource),
    [STATUS]: webSocketResource<SystemStatusResource>(normalizeSystemStatusResource),
    [POWER_OPERATIONS]: (manager) => ({
        fetch: manager.createApiFetcher('/api/v1/system/power/operations/active'),
        transform: decodeActivePowerOperationResponse
    }),
    [METRICS]: webSocketResource<SystemMetricsResponse>(decodeSystemMetricsResponse),
    [LOGS_CORE]: webSocketResource<LogsResource>(decodeLogsResource),
    [WEBUI_NOTIFICATIONS]: webSocketResource<NotificationsResource>(decodeNotificationsResource),
    [WEBUI_CHAT_ATTENTION]: webSocketResource<ConversationAttentionResource>(decodeConversationAttentionResource),
    [WEBUI_CHAT_ACTIVITY]: webSocketResource<ChatStreamActivityResource>(decodeChatStreamActivityResource),
    [HARDWARE]: webSocketResource<HardwareSnapshotResource>(decodeHardwareSnapshotResource),
    [HARDWARE_GPU_CAPABILITIES]: (_manager) => ({
        websocketOnly: true,
        normalize: normalizeGpuCapabilitiesResource
    }),
    [HARDWARE_GPU_SLOTS]: (manager) => manager.createGpuSlotsResource(),
    [HARDWARE_GPU_SOAIBENCH_RUNS]: (_manager) => createSoAIBenchRunsResource(),
    [HARDWARE_PROCESSES]: webSocketResource<HardwareProcessesResource>(decodeHardwareProcessesResource)
});

export { DEFAULT_RESOURCE_FACTORIES };
