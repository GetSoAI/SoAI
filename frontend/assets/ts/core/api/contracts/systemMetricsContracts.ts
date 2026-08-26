/* SoAI - Frontend system metrics API contracts [frontend/assets/ts/core/api/contracts/systemMetricsContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeMcpRagMetrics, decodeMcpRemoteMetrics, decodeMcpSearchMetrics, decodeMcpServerMetrics } from '@core/realtime/streammanager/resources/systemMetricsMcpContracts.ts';
import { decodeMetricsCapabilities, decodeTokenRates, type MetricsCapabilities } from '@core/realtime/streammanager/resources/systemMetricsMetadataContracts.ts';
import { decodeBillingMetrics, decodeDirectorMetrics, decodeInactivityMetrics, decodeOrchestratorMetrics, decodePluginMetrics, decodeUsageMetrics } from '@core/realtime/streammanager/resources/systemMetricsOrchestrationContracts.ts';
import { decodeApiMetrics, decodeDatabaseMetrics, decodeDownloadSpeedMetrics, decodeEventBusMetrics, decodeGenesisMetrics, decodeGlobalMetrics, decodeModelManagerMetrics, decodeStateMetrics, decodeStreamingMetrics, decodeWebsocketMetrics } from '@core/realtime/streammanager/resources/systemMetricsRuntimeContracts.ts';
import { assignOptionalSection, decodeFiniteNumberFields, optionalMetricsObject } from '@core/realtime/streammanager/resources/systemMetricsValueDecoding.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

type SystemMetricsResponse = JsonObject & {
    global?: JsonObject & { startTimeMs?: number; restartsTriggered?: number; updatesTriggered?: number };
    billing?: JsonObject & { totalTokensGenerated?: number; tokensByModel?: JsonObject; tokensByPlugin?: JsonObject; tokensByClient?: JsonObject };
    genesis?: JsonObject & { requestsTotal?: number; tokensTotal?: number; uptimeMs?: number };
    director?: JsonObject & {
        gauges?: JsonObject & { queueSize?: number; requestLatencyMs?: number; pluginHealth?: JsonObject; pendingLoads?: number; pluginConcurrencyActive?: JsonObject };
        modelLoads?: JsonObject;
        requests?: JsonObject;
        requestsByModel?: JsonObject;
        requestsByVirtualModel?: JsonObject;
    };
    api?: JsonObject;
    database?: JsonObject;
    eventBus?: JsonObject;
    streaming?: JsonObject;
    websocket?: JsonObject;
    state?: JsonObject;
    plugins?: JsonObject;
    usage?: JsonObject & { byPlugin?: JsonObject; byModel?: JsonObject; byClient?: JsonObject };
    models?: JsonObject & { available?: number };
    modelManager?: JsonObject;
    orchestrator?: JsonObject;
    inactivityMonitor?: JsonObject;
    downloadSpeed?: JsonObject;
    mcpServer?: JsonObject;
    mcpRemote?: JsonObject;
    mcpSearch?: JsonObject;
    mcpRag?: JsonObject;
    capabilities?: MetricsCapabilities;
    tokenRates?: JsonObject;
};

const decodeSystemMetricsResponse = (value: ApiResponsePayload): SystemMetricsResponse => {
    if (!isJsonObject(value)) throw new TypeError('system.metrics snapshot payload must be an object');
    const globalWire = value['global'];
    if (isJsonObject(globalWire) && ('startTimeMs' in globalWire || 'restartsTriggered' in globalWire || 'updatesTriggered' in globalWire)) throw new TypeError('system.metrics.global must use canonical V1 wire fields');
    const decoded: SystemMetricsResponse = {};
    assignOptionalSection(decoded, 'global', decodeGlobalMetrics(value));
    assignOptionalSection(decoded, 'eventBus', decodeEventBusMetrics(value));
    assignOptionalSection(decoded, 'director', decodeDirectorMetrics(value));
    assignOptionalSection(decoded, 'orchestrator', decodeOrchestratorMetrics(value));
    assignOptionalSection(decoded, 'api', decodeApiMetrics(value));
    assignOptionalSection(decoded, 'streaming', decodeStreamingMetrics(value));
    assignOptionalSection(decoded, 'websocket', decodeWebsocketMetrics(value));
    assignOptionalSection(decoded, 'modelManager', decodeModelManagerMetrics(value));
    assignOptionalSection(decoded, 'state', decodeStateMetrics(value));
    assignOptionalSection(decoded, 'plugins', decodePluginMetrics(value));
    assignOptionalSection(decoded, 'billing', decodeBillingMetrics(value));
    assignOptionalSection(decoded, 'usage', decodeUsageMetrics(value));
    assignOptionalSection(decoded, 'inactivityMonitor', decodeInactivityMetrics(value));
    assignOptionalSection(decoded, 'database', decodeDatabaseMetrics(value));
    assignOptionalSection(decoded, 'downloadSpeed', decodeDownloadSpeedMetrics(value));
    assignOptionalSection(decoded, 'genesis', decodeGenesisMetrics(value));
    assignOptionalSection(decoded, 'mcpServer', decodeMcpServerMetrics(value));
    assignOptionalSection(decoded, 'mcpRemote', decodeMcpRemoteMetrics(value));
    assignOptionalSection(decoded, 'mcpSearch', decodeMcpSearchMetrics(value));
    assignOptionalSection(decoded, 'mcpRag', decodeMcpRagMetrics(value));
    const capabilities = decodeMetricsCapabilities(value);
    if (capabilities) decoded.capabilities = capabilities;
    assignOptionalSection(decoded, 'tokenRates', decodeTokenRates(value));
    const models = optionalMetricsObject(value, 'models', 'system.metrics');
    if (models) decoded.models = decodeFiniteNumberFields(models, { available: 'available' }, 'system.metrics.models');
    return decoded;
};

export { decodeSystemMetricsResponse };
export type { SystemMetricsResponse };
