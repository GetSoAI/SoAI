/* SoAI - Model domain type declarations [frontend/assets/ts/core/types/modelTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceIncomingObject } from '@core/data/clientdatahub/types.ts';

const MODEL_CONTEXT_WINDOW_PARAMETER_KEY = 'context_window_tokens';

export interface ModelRecord extends ResourceIncomingObject {
    id?: string;
    name?: string;
    universalId?: string;
    modelId?: string;
    sourceModelId?: string;
    rawUpstreamModelId?: string;
    alias?: string;
    displayName?: string;
    hasAlias?: boolean;
    description?: string;
    type?: string;
    plugin?: string;
    pluginName?: string;
    provider?: JsonValue;
    providerId?: string;
    providerName?: string;
    pluginStatus?: string;
    state?: string;
    status?: string;
    statusMessage?: string;
    newState?: string;
    path?: string;
    sizeBytes?: number;
    family?: string;
    quantization?: string;
    license?: string;
    createdAtMs?: number;
    lastModifiedAtMs?: number;
    lastDiscoveredAtMs?: number;
    fileModifiedAtMs?: number;
    isLoaded?: boolean;
    loaded?: boolean;
    isEnabled?: boolean;
    isAvailable?: boolean;
    available?: boolean;
    isOrphaned?: boolean;
    requestCount?: number;
    averageTokens?: number;
    successRate?: number;
    lastUsedAtMs?: number;
    openaiCapabilities?: JsonObject;
    openaiCapabilitiesOverrides?: JsonValue | null;
    modalities?: string[];
    capabilities?: JsonValue[];
    tags?: JsonValue[];
    modelRepository?: string;
    strategy?: string;
    models?: JsonValue[];
    constituents?: number;
    providerMetadata?: JsonValue;
    websiteBackend?: string;
    backendDocumentation?: string;
    modelHasCustomParameters?: boolean;
    hasCustomParameters?: boolean;
    modelType?: string;
    contextWindowTokens?: number;
    parameterVersion?: number;
    size?: number;
}

export interface ModelData extends ModelRecord {
    id: string;
    name: string;
}

export { MODEL_CONTEXT_WINDOW_PARAMETER_KEY };
