/* SoAI - Shared model actions contracts [frontend/assets/ts/core/modelactions/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RemoteModelSearchResult } from '@core/api/contracts/pluginSearchContracts.ts';
import type { ModelAliasUpdateRequest } from '@core/api/contracts/modelOperationContracts.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { RequestOptions } from '@core/api/types/request.ts';

interface StreamManagerInterface {
    taskAction: (endpoint: string, options: StreamActionOptions) => StreamActionHandle;
    taskCommand: (command: JsonObject, options: StreamCommandOptions) => StreamActionHandle;
}

interface StreamActionOptions {
    method: string;
    body?: JsonValue | null | undefined;
    handlers: StreamActionHandlers;
    operation?: OperationMeta | null;
}

interface StreamCommandOptions {
    handlers: StreamActionHandlers;
    operation?: OperationMeta | null;
}

interface OperationMeta {
    type: string;
    plugin?: string | null | undefined;
    pluginName?: string | null | undefined;
    modelId?: string | null | undefined;
    universalId?: string | null | undefined;
    modelName?: string | null | undefined;
    quantization?: string | null | undefined;
    cancelable?: boolean | undefined;
}

interface DownloadParameters {
    plugin?: string;
    modelId?: string;
    universalId?: string;
    quantization?: string;
    displayName?: string;
    modelName?: string;
}

interface DownloadPayload {
    universalId?: string | undefined;
    plugin?: string | undefined;
    modelId?: string | undefined;
    quantization?: string | undefined;
}

interface RunStreamOptions {
    method?: string;
    body?: JsonValue | null | undefined;
    handlers?: StreamActionHandlers;
    operation?: OperationMeta | null;
}

interface SearchOptions {
    limit?: number;
    signal?: AbortSignal;
}

interface ApiInterface {
    whenReady?: (options: { allowDiscovery: boolean }) => Promise<string>;
    models?: {
        getVariants: (plugin: string, modelId: string, options: Record<string, JsonValue | null | undefined>) => Promise<ModelVariantResponse[]>;
        updateAlias: (id: string, request: ModelAliasUpdateRequest) => Promise<SuccessfulMutationResponse>;
        deleteAlias: (id: string) => Promise<SuccessfulMutationResponse>;
    };
    plugins?: {
        searchModels: (plugin: string, query: string, options: RequestOptions & { limit: number }) => Promise<RemoteModelSearchResult[]>;
    };
}

export type { ApiInterface, DownloadParameters, DownloadPayload, OperationMeta, RunStreamOptions, SearchOptions, StreamActionOptions, StreamCommandOptions, StreamManagerInterface };
