/* SoAI - Shared frontend API endpoint layer plugins [frontend/assets/ts/core/api/endpoints/plugins.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeModelsFilter, normalizeNonEmptyString } from '@core/api/apiNormalizers.ts';
import { decodeBackendVariantsResponse, decodePluginBackendUpdatesResponse, decodePluginCompatibilityOverrideResponse, serializeBackendVariantSelectionRequest, type BackendVariantsResponse, type PluginBackendUpdatesResponse, type PluginCompatibilityOverrideResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import { decodeManualInstallPathResponse, type ManualInstallPathResponse } from '@core/api/contracts/manualInstallPathContracts.ts';
import { decodeExternalProviderCreateResponse, decodeExternalProviderListResponse, decodeExternalProviderRecord, type ExternalProviderCreateResponse, type ExternalProviderRecord } from '@core/api/contracts/pluginProviderContracts.ts';
import { decodeRemoteModelSearchResponse, type RemoteModelSearchResult } from '@core/api/contracts/pluginSearchContracts.ts';
import { decodeSuccessfulMutationResponse, type SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { decodeModelTaskAcceptedResponse, type ModelTaskAcceptedResponse } from '@core/api/contracts/modelOperationContracts.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiQueryParameters } from '@core/api/types/request.ts';
import type { ProviderAddOptions, ProviderUpdateOptions, SearchModelsOptions } from '@core/api/types/plugins.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { executeMutationWithClockRecovery } from '@core/mutations/mutationExecution.ts';
import { serializeProviderMutation } from '@core/plugins/pluginMutationContracts.ts';
import { isDefined, isFiniteNumber, isNullOrUndefined, isNumber } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const createPluginsEndpoints = (
    api: ApiClientContext
): {
    manualInstall: () => Promise<ManualInstallPathResponse>;
    searchModels: (name: string, query: string, options?: SearchModelsOptions) => Promise<RemoteModelSearchResult[]>;
    delete: (name: string, deleteModels?: boolean) => Promise<ModelTaskAcceptedResponse>;
    overrideIncompatibility: (name: string, override: boolean) => Promise<PluginCompatibilityOverrideResponse>;
    getBackendVariants: (name: string) => Promise<BackendVariantsResponse>;
    saveBackendVariantSelection: (name: string, variantId: string) => Promise<BackendVariantsResponse>;
    checkUpdates: () => Promise<PluginBackendUpdatesResponse>;
    resetCircuitBreaker: (name: string) => Promise<SuccessfulMutationResponse>;
    providers: { list: (name: string) => Promise<ExternalProviderRecord[]>; add: (name: string, options: ProviderAddOptions) => Promise<ExternalProviderCreateResponse>; update: (pName: string, pId: string, revision: number, updates: ProviderUpdateOptions) => Promise<ExternalProviderRecord>; delete: (pName: string, pId: string, revision: number) => Promise<void> };
} => {
    return {
        manualInstall: async (): Promise<ManualInstallPathResponse> => decodeManualInstallPathResponse(await api.get('/api/v1/plugins/manual-install'), 'plugins'),
        searchModels: async (name: string, query: string, options: SearchModelsOptions = {}): Promise<RemoteModelSearchResult[]> => {
            const pluginName = toTrimmedString(name);
            if (!pluginName) throw new Error('plugins.searchModels requires a plugin name');
            const searchQuery = toTrimmedString(query);
            if (!searchQuery) throw new Error('plugins.searchModels requires a query string');
            const queryParameters: ApiQueryParameters = { q: searchQuery };
            if (isNumber(options.limit) && isFiniteNumber(options.limit)) queryParameters['limit'] = options.limit;
            return decodeRemoteModelSearchResponse(
                await api.get(`/api/v1/plugins/${api.encodePathSegment(pluginName)}/model-search`, {
                    query: queryParameters,
                    ...buildSignalRequestOptions(options)
                })
            );
        },
        delete: async (name: string, deleteModels: boolean = false): Promise<ModelTaskAcceptedResponse> => decodeModelTaskAcceptedResponse(await api.delete(`/api/v1/plugins/${api.encodePathSegment(name)}`, { query: { 'delete_models': deleteModels } })),
        overrideIncompatibility: async (name: string, override: boolean): Promise<PluginCompatibilityOverrideResponse> => decodePluginCompatibilityOverrideResponse(await api.post(`/api/v1/plugins/${api.encodePathSegment(name)}/override-incompatibility`, { override })),
        getBackendVariants: async (name: string): Promise<BackendVariantsResponse> => decodeBackendVariantsResponse(await api.get(`/api/v1/plugins/${api.encodePathSegment(name)}/backend-variants`)),
        saveBackendVariantSelection: async (name: string, variantId: string): Promise<BackendVariantsResponse> => decodeBackendVariantsResponse(await api.put(`/api/v1/plugins/${api.encodePathSegment(name)}/backend-variant-selection`, serializeBackendVariantSelectionRequest(variantId))),
        checkUpdates: async (): Promise<PluginBackendUpdatesResponse> => decodePluginBackendUpdatesResponse(await api.post('/api/v1/actions/plugins/check-for-updates')),
        resetCircuitBreaker: async (name: string): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.post(`/api/v1/system/plugins/${api.encodePathSegment(name)}/reset-circuit-breaker`), 'Plugin circuit breaker reset response'),
        providers: {
            list: async (name: string): Promise<ExternalProviderRecord[]> => decodeExternalProviderListResponse(await api.get(`/api/v1/plugins/${api.encodePathSegment(name)}/providers`)),
            add: async (name: string, options: ProviderAddOptions): Promise<ExternalProviderCreateResponse> => {
                const payload: JsonObject = {};
                const url = normalizeNonEmptyString(options.apiUrl);
                if (!url) throw new Error('Provider apiUrl is required');
                payload['api_url'] = url;
                if (!isNullOrUndefined(options.name)) payload['name'] = options.name;
                if (isDefined(options.apiKey)) payload['api_key'] = options.apiKey;
                const filter = normalizeModelsFilter(options.modelsFilter);
                if (isDefined(filter)) payload['models_filter'] = filter;
                return executeMutationWithClockRecovery(async (operationId): Promise<ExternalProviderCreateResponse> => {
                    const mutation = serializeProviderMutation({ operation: 'create', operationId, body: payload });
                    return decodeExternalProviderCreateResponse(await api.post(`/api/v1/plugins/${api.encodePathSegment(name)}/providers`, mutation.body, { headers: mutation.headers }));
                });
            },
            update: async (pName: string, pId: string, revision: number, updates: ProviderUpdateOptions): Promise<ExternalProviderRecord> => {
                const payload: JsonObject = {};
                if (!isNullOrUndefined(updates.name)) payload['name'] = updates.name;
                if (isDefined(updates.apiKey)) payload['api_key'] = updates.apiKey;
                const filter = normalizeModelsFilter(updates.modelsFilter);
                if (isDefined(filter)) payload['models_filter'] = filter;
                return executeMutationWithClockRecovery(async (operationId): Promise<ExternalProviderRecord> => {
                    const mutation = serializeProviderMutation({ operation: 'update', operationId, revision, body: payload });
                    return decodeExternalProviderRecord(await api.patch(`/api/v1/plugins/${api.encodePathSegment(pName)}/providers/${api.encodePathSegment(pId)}`, mutation.body, { headers: mutation.headers }), 'External provider update response');
                });
            },
            delete: async (pName: string, pId: string, revision: number): Promise<void> => {
                await executeMutationWithClockRecovery(async (operationId): Promise<void> => {
                    const mutation = serializeProviderMutation({ operation: 'delete', operationId, revision, body: {} });
                    decodeNoContentResponse(await api.delete(`/api/v1/plugins/${api.encodePathSegment(pName)}/providers/${api.encodePathSegment(pId)}`, { headers: mutation.headers, body: mutation.body }), 'External provider delete response');
                });
            }
        }
    };
};

export { createPluginsEndpoints };
