/* SoAI - Frontend model catalog contract types [frontend/assets/ts/core/api/contracts/modelCatalogContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ModelCatalogProvider {
    id: string;
    name: string | null;
    apiUrl: string | null;
    status: string | null;
    lastError: string | null;
    lastCheckedAtMs: number | null;
    contextWindowTokens: number | null;
    createdAtMs: number | null;
}

interface LocalModelCatalogEntry {
    id: string;
    name: string;
    plugin: string;
    modelId: string;
    universalId: string;
    type: string;
    hasAlias: boolean;
    modelRepository: string | null;
    description: string | null;
    isLoaded: boolean;
    pluginStatus: string;
    status: string;
    isEnabled: boolean;
    isAvailable: boolean;
    modelHasCustomParameters: boolean;
    parameterVersion: number;
    isOrphaned: boolean;
    statusMessage: string;
    createdAtMs: number | null;
    lastModifiedAtMs: number | null;
    lastDiscoveredAtMs: number | null;
    lastUsedAtMs: number | null;
    fileModifiedAtMs: number | null;
    requestCount: number;
    sizeBytes: number | null;
    path: string | null;
    family: string | null;
    license: string | null;
    quantization: string | null;
    capabilities: JsonValue[];
    tags: JsonValue[];
    provider: ModelCatalogProvider | null;
    providerId: string | null;
    providerMetadata: ModelCatalogProvider | null;
    sourceModelId: string;
    rawUpstreamModelId: string | null;
    openaiCapabilitiesOverrides: JsonObject | null;
    modalities: string[];
    openaiCapabilities: JsonObject | null;
    modelType: string | null;
    contextWindowTokens: number | null;
}

interface VirtualModelCatalogConstituent {
    universalId: string;
    parameters: JsonObject;
}

interface VirtualModelCatalogEntry {
    id: string;
    name: string;
    type: 'virtual';
    modelType: 'virtual';
    strategy: 'load_balancing' | 'failover';
    models: VirtualModelCatalogConstituent[];
    isEnabled: boolean;
    modalities: string[];
    openaiCapabilities: JsonObject | null;
    contextWindowTokens: number | null;
}

type ModelCatalogEntry = LocalModelCatalogEntry | VirtualModelCatalogEntry;
type ModelCatalogResponse = Record<string, ModelCatalogEntry[]>;

export type { LocalModelCatalogEntry, ModelCatalogEntry, ModelCatalogProvider, ModelCatalogResponse, VirtualModelCatalogConstituent, VirtualModelCatalogEntry };
