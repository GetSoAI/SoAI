/* SoAI - Typed stream resource registry [frontend/assets/ts/core/realtime/streammanager/resourceRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemStatusResponse } from '@core/api/contracts/systemContracts.ts';
import type { PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import type { ConversationAttentionResource } from '@core/chat/conversationAttentionSnapshot.ts';
import type { ChatStreamActivityResource } from '@core/chat/chatStreamActivitySnapshot.ts';
import type { GpuCapabilitiesResource, GpuSlotsResource, HardwareProcessesResource, HardwareSnapshotResource, LogsResource, ModelsResource, NotificationsResource, PluginCapabilitiesResource, PluginsResource, PromptsResource, ProvidersResource, RoutingConfigResource, SoAIBenchRunsState, SystemMetricsResponse, VirtualModelsResource } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { LatestUsageResource } from '@core/realtime/streammanager/resources/latestUsageResource.ts';

type SystemStatusResource = Omit<SystemStatusResponse, 'mainState'> & { mainState: string };

interface StreamResourceRegistry {
    'models.collection': ModelsResource;
    'plugins.collection': PluginsResource;
    'models.last_used': LatestUsageResource;
    'plugins.last_used': LatestUsageResource;
    'prompts.collection': PromptsResource;
    'providers.collection': ProvidersResource;
    'hardware.snapshot': HardwareSnapshotResource;
    'hardware.gpu.capabilities': GpuCapabilitiesResource;
    'hardware.gpu.slots': GpuSlotsResource;
    'hardware.gpu.soaibench.runs': SoAIBenchRunsState;
    'hardware.processes': HardwareProcessesResource;
    'system.status': SystemStatusResource;
    'system.power.operations': PowerOperationResponse;
    'system.metrics': SystemMetricsResponse;
    'system.logs.core': LogsResource;
    'plugins.capabilities.manifest': PluginCapabilitiesResource;
    'routing.config': RoutingConfigResource;
    'routing.virtualModels': VirtualModelsResource;
    'webui.notifications': NotificationsResource;
    'webui.chat.attention': ConversationAttentionResource;
    'webui.chat.activity': ChatStreamActivityResource;
}

type StreamResourceId = keyof StreamResourceRegistry;
type StreamResourceValue<ResourceId extends string> = ResourceId extends StreamResourceId ? StreamResourceRegistry[ResourceId] : JsonValue;

export type { StreamResourceId, StreamResourceRegistry, StreamResourceValue, SystemStatusResource };
