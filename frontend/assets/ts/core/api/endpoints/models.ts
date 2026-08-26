/* SoAI - Shared frontend API endpoint layer models [frontend/assets/ts/core/api/endpoints/models.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { GetVariantsOptions, ModelDownloadParameters } from '@core/api/types/models.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { OpenAICapabilityOverrideCategory } from '@core/openai/capabilityCategories.ts';
import { isBoolean } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { decodeSuccessfulMutationResponse, type SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { decodeManualInstallPathResponse, type ManualInstallPathResponse } from '@core/api/contracts/manualInstallPathContracts.ts';
import { decodeModelDiscoveryResponse, decodeModelTaskAcceptedResponse, serializeModelAliasUpdateRequest, type ModelAliasUpdateRequest, type ModelDiscoveryResponse, type ModelTaskAcceptedResponse } from '@core/api/contracts/modelOperationContracts.ts';
import { decodeModelVariantsResponse, type ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import { decodeModelCatalogResponse, type ModelCatalogResponse } from '@core/api/contracts/modelCatalogContracts.ts';

const MODELS_BASE_PATH = '/api/v1/models';

const createModelsEndpoints = (
    api: ApiClientContext
): {
    list: (options?: RequestOptions) => Promise<ModelCatalogResponse>;
    manualInstall: () => Promise<ManualInstallPathResponse>;
    delete: (id: string) => Promise<ModelTaskAcceptedResponse>;
    download: (parameters?: ModelDownloadParameters) => Promise<ModelTaskAcceptedResponse>;
    updateAlias: (id: string, request: ModelAliasUpdateRequest) => Promise<SuccessfulMutationResponse>;
    deleteAlias: (id: string) => Promise<SuccessfulMutationResponse>;
    updateEnabled: (id: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>;
    updateParameters: (id: string, parameters: JsonValue) => Promise<SuccessfulMutationResponse>;
    deleteParameters: (id: string, keys: string[]) => Promise<SuccessfulMutationResponse>;
    updateOpenAICapabilityOverride: (id: string, payload: { category: OpenAICapabilityOverrideCategory; token: string; enabled: boolean }) => Promise<SuccessfulMutationResponse>;
    resetOpenAICapabilityOverrides: (id: string) => Promise<SuccessfulMutationResponse>;
    discover: () => Promise<ModelDiscoveryResponse>;
    getVariants: (pluginName: string, modelId: string, options?: GetVariantsOptions) => Promise<ModelVariantResponse[]>;
} => {
    return {
        list: async (options: RequestOptions = {}): Promise<ModelCatalogResponse> => decodeModelCatalogResponse(await api.get(MODELS_BASE_PATH, options)),
        manualInstall: async (): Promise<ManualInstallPathResponse> => decodeManualInstallPathResponse(await api.get(`${MODELS_BASE_PATH}/manual-install`), 'models'),
        delete: async (id: string): Promise<ModelTaskAcceptedResponse> => decodeModelTaskAcceptedResponse(await api.delete(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}`)),
        download: async (parameters: ModelDownloadParameters = {}): Promise<ModelTaskAcceptedResponse> => {
            const payload: Record<string, string> = {};
            const universalId = toTrimmedString(parameters.universalId);
            const plugin = toTrimmedString(parameters.plugin);
            const modelId = toTrimmedString(parameters.modelId);
            const quantization = toTrimmedString(parameters.quantization);
            if (universalId) payload['universal_id'] = universalId;
            else if (plugin && modelId) {
                payload['plugin'] = plugin;
                payload['model_id'] = modelId;
            } else throw new Error('Model download requires a universalId or both plugin and modelId.');
            if (quantization) payload['quantization'] = quantization;
            return decodeModelTaskAcceptedResponse(await api.post(`${MODELS_BASE_PATH}/download`, payload));
        },
        updateAlias: async (id: string, request: ModelAliasUpdateRequest): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.patch(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/alias`, serializeModelAliasUpdateRequest(request)), 'Model alias update response'),
        deleteAlias: async (id: string): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.delete(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/alias`), 'Model alias deletion response'),
        updateEnabled: async (id: string, payload: { enabled: boolean }): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.patch(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/enabled`, payload), 'Model enabled update response'),
        updateParameters: async (id: string, parameters: JsonValue): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.patch(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/parameters`, { parameters }), 'Model parameters update response'),
        deleteParameters: async (id: string, keys: string[]): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.delete(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/parameters`, { body: { keys } }), 'Model parameters deletion response'),
        updateOpenAICapabilityOverride: async (id: string, payload: { category: OpenAICapabilityOverrideCategory; token: string; enabled: boolean }): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.patch(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/capabilities/openai`, payload), 'Model OpenAI capability update response'),
        resetOpenAICapabilityOverrides: async (id: string): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.delete(`${MODELS_BASE_PATH}/${api.encodePathSegment(id)}/capabilities/openai`), 'Model OpenAI capability reset response'),
        discover: async (): Promise<ModelDiscoveryResponse> => decodeModelDiscoveryResponse(await api.post('/api/v1/actions/discover-models')),
        getVariants: async (pluginName: string, modelId: string, options: GetVariantsOptions = {}): Promise<ModelVariantResponse[]> => {
            const query: Record<string, boolean> = {};
            if (isBoolean(options.includeSpeedTests)) query['include_speed_tests'] = options.includeSpeedTests;
            return decodeModelVariantsResponse(await api.get(`/api/v1/plugins/${api.encodePathSegment(pluginName)}/models/${api.encodePathSegment(modelId)}/variants`, { query }));
        }
    };
};

export { MODELS_BASE_PATH, createModelsEndpoints };
