/* SoAI - Frontend realtime resource value contracts [frontend/assets/ts/core/realtime/streammanager/resources/resourceValueContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareSnapshotResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { SystemMetricsResponse } from '@core/api/contracts/systemMetricsContracts.ts';
import type { ExternalProviderRecord } from '@core/api/contracts/pluginProviderContracts.ts';
import type { PromptResponse } from '@core/api/contracts/promptContracts.ts';
import type { VirtualModelResponse } from '@core/api/contracts/virtualModelContracts.ts';
import type { NotificationsListResponse } from '@core/notifications/types.ts';
import type { PluginCollectionEntry } from '@core/plugins/collectionSnapshot.ts';
import type { LogSnapshotResult } from '@core/realtime/streammanager/types.ts';
import type { SoAIBenchRunsState } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';
import type { GpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSlotsBuilderResult, ModelData } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type ModelsResource = ModelData[] & JsonValue;
type PluginsResource = PluginCollectionEntry[];
type PromptsResource = PromptResponse[] & JsonValue;
type ProvidersResource = ExternalProviderRecord[] & JsonValue;
type HardwareSnapshotResource = HardwareSnapshotResponse & JsonObject;
type GpuSlotsResource = GpuSlotsBuilderResult & JsonObject;
type HardwareProcessRecord = JsonObject & {
    pid: number;
    name: string;
    username: string;
    cpuPercent: number;
    memoryMb: number;
    swapMb: number | null;
    swapKnown: boolean;
    createTimeMs: number;
};
type HardwareProcessesResource = HardwareProcessRecord[];
type LogsResource = LogSnapshotResult & JsonObject;
type PluginCapabilitiesResource = JsonObject;
type RoutingConfigResource = JsonObject & {
    traceId?: string;
    eventId?: string;
    timestamp?: JsonValue;
    virtualModels?: VirtualModelsResource;
    failovers?: JsonObject[];
    routingConfig?: JsonObject;
};
type VirtualModelsResource = VirtualModelResponse[] & JsonValue;
type NotificationsResource = NotificationsListResponse & JsonObject;

export type { GpuCapabilitiesResource, GpuSlotsResource, HardwareProcessRecord, HardwareProcessesResource, HardwareSnapshotResource, LogsResource, ModelsResource, NotificationsResource, PluginCapabilitiesResource, PluginsResource, PromptsResource, ProvidersResource, RoutingConfigResource, SoAIBenchRunsState, SystemMetricsResponse, VirtualModelsResource };
