/* SoAI - Frontend model action ownership [frontend/assets/ts/core/modelactions/modelActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modelPath } from '@core/api/endpoints/uiPaths.ts';
import type { ModelAliasUpdateRequest } from '@core/api/contracts/modelOperationContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { getApiClient, type ApiClient } from '@core/api/service.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import type { RemoteModelSearchResult } from '@core/api/contracts/pluginSearchContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ApiInterface, DownloadParameters, OperationMeta, RunStreamOptions, SearchOptions, StreamManagerInterface } from '@core/modelactions/contracts.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

const isStreamManagerInterface = <TCandidate>(candidate: TCandidate): candidate is TCandidate & StreamManagerInterface => {
    if (!isObject(candidate)) return false;
    return 'taskAction' in candidate && isFunction(candidate.taskAction) && 'taskCommand' in candidate && isFunction(candidate.taskCommand);
};

const validateStreamManager = <TCandidate>(candidate: TCandidate): StreamManagerInterface => {
    if (!isStreamManagerInterface(candidate)) {
        throw new Error('core.streamTasks must be initialized before model actions');
    }
    return candidate;
};

let streamManagerReadiness: Promise<StreamManagerInterface> | null = null;

const resolveStreamManager = async (): Promise<StreamManagerInterface> => {
    if (!streamManagerReadiness) {
        const runtime = getStreamRuntime();
        const manager = validateStreamManager(runtime.tasks);
        streamManagerReadiness = (async () => {
            try {
                await ensureStreamManagerReady(runtime.resources, { allowDiscovery: true });
                return manager;
            } catch (error) {
                streamManagerReadiness = null;
                const runtimeError = ensureError(error);
                errorHandler.error('CoreModelActions', 'Stream manager initialization failed', runtimeError);
                throw runtimeError;
            }
        })();
    }
    return streamManagerReadiness;
};

const ensureApi = async (): Promise<ApiInterface> => {
    const isApiInterface = (value: ApiClient | ApiInterface | JsonValue | null | undefined): value is ApiInterface => isObject(value);
    const api = getApiClient();
    if (!isApiInterface(api)) {
        throw new Error('core.apiClient must be available for model actions');
    }
    if (isFunction(api.whenReady)) {
        await api.whenReady({ allowDiscovery: true });
    }
    return api;
};

const normalizeDownloadPayload = (parameters: DownloadParameters): JsonObject => {
    const payload: JsonObject = {};
    if (parameters.universalId) {
        payload['universal_id'] = parameters.universalId;
    } else {
        if (!parameters.plugin || !parameters.modelId) {
            throw new Error('Model download requires universalId or both plugin and modelId');
        }
        payload['plugin'] = parameters.plugin;
        payload['model_id'] = parameters.modelId;
    }
    if (parameters.quantization) {
        payload['quantization'] = parameters.quantization;
    }
    return payload;
};

const runTaskAction = async (endpoint: string, options: RunStreamOptions = {}): Promise<StreamActionHandle> => {
    const manager = await resolveStreamManager();
    const { method = 'POST', body = null, handlers = {}, operation = null } = options;
    return manager.taskAction(endpoint, { method, body, handlers, operation });
};

const runTaskCommand = async (command: JsonObject, options: { handlers?: StreamActionHandlers; operation?: OperationMeta | null } = {}): Promise<StreamActionHandle> => {
    const manager = await resolveStreamManager();
    const { handlers = {}, operation = null } = options;
    return manager.taskCommand(command, { handlers, operation });
};

const modelActions = Object.freeze({
    async probeModelVariants(plugin: string, modelId: string): Promise<Array<ModelVariantResponse>> {
        const normalizedPlugin = isString(plugin) ? plugin.trim() : '';
        const normalizedModel = isString(modelId) ? modelId.trim() : '';
        if (!normalizedPlugin || !normalizedModel) {
            throw new Error('Variant probe requires plugin and modelId');
        }
        const api = await ensureApi();
        if (!api.models?.getVariants) {
            throw new Error('core.apiClient is missing models.getVariants');
        }
        const result = await api.models.getVariants(normalizedPlugin, normalizedModel, { includeSpeedTests: true });
        if (result === undefined) {
            throw new Error('core.apiClient.models.getVariants must return a value');
        }
        return result;
    },

    async searchRemoteModels(plugin: string, query: string, options: SearchOptions = {}): Promise<RemoteModelSearchResult[]> {
        const normalizedPlugin = isString(plugin) ? plugin.trim() : '';
        const normalizedQuery = isString(query) ? query.trim() : '';
        if (!normalizedPlugin || !normalizedQuery) {
            throw new Error('Remote model search requires plugin and query');
        }
        const api = await ensureApi();
        if (!api.plugins?.searchModels) {
            throw new Error('core.apiClient is missing plugins.searchModels');
        }
        const limit = isFiniteNumber(options.limit) ? options.limit : 10;
        const requestOptions: { limit: number; signal?: AbortSignal | undefined } = { limit };
        if (options.signal) {
            requestOptions['signal'] = options.signal;
        }
        const result = await api.plugins.searchModels(normalizedPlugin, normalizedQuery, requestOptions);
        if (result === undefined) {
            throw new Error('core.apiClient.plugins.searchModels must return a value');
        }
        return result;
    },

    startDownload(parameters: DownloadParameters = {}, options: { handlers?: StreamActionHandlers } = {}): Promise<StreamActionHandle> {
        const { plugin, modelId, universalId } = parameters;
        if (!universalId && (!plugin || !modelId)) {
            throw new Error('Model download requires universalId or both plugin and modelId');
        }
        const payload = normalizeDownloadPayload(parameters);
        const payloadPlugin = isString(payload['plugin']) ? payload['plugin'] : null;
        const payloadModelId = isString(payload['model_id']) ? payload['model_id'] : null;
        const operationMeta: OperationMeta = {
            type: 'model-download',
            plugin: plugin || payloadPlugin,
            pluginName: plugin || payloadPlugin,
            modelId: modelId || payloadModelId,
            universalId: universalId || null,
            modelName: parameters.displayName || parameters.modelName || null,
            quantization: parameters.quantization || null
        };
        if (isString(operationMeta.plugin)) {
            operationMeta.plugin = operationMeta.plugin.trim();
            operationMeta.pluginName = operationMeta.plugin;
            if (!operationMeta.plugin) {
                operationMeta.plugin = null;
                operationMeta.pluginName = null;
            }
        }
        return runTaskCommand(
            { type: WEBSOCKET_MESSAGE_TYPES.MODEL_DOWNLOAD, body: payload },
            {
                handlers: options.handlers ?? {},
                operation: operationMeta
            }
        );
    },

    delete(universalId: string, options: { handlers?: StreamActionHandlers } = {}): Promise<StreamActionHandle> {
        if (!universalId) {
            throw new Error('Model deletion requires universalId');
        }
        const operationMeta: OperationMeta = {
            type: 'model-delete',
            universalId,
            cancelable: false
        };
        return runTaskAction(modelPath(universalId), {
            method: 'DELETE',
            handlers: options.handlers ?? {},
            operation: operationMeta
        });
    },

    async updateAlias(universalId: string, request: ModelAliasUpdateRequest): Promise<SuccessfulMutationResponse> {
        if (!universalId) {
            throw new Error('Model alias update requires universalId');
        }
        const api = await ensureApi();
        if (!api.models?.updateAlias) {
            throw new Error('core.apiClient is missing models.updateAlias');
        }
        const result = await api.models.updateAlias(universalId, request);
        if (result === undefined) {
            throw new Error('core.apiClient.models.updateAlias must return a value');
        }
        return result;
    },

    async removeAlias(universalId: string): Promise<SuccessfulMutationResponse> {
        if (!universalId) {
            throw new Error('Model alias removal requires universalId');
        }
        const api = await ensureApi();
        if (!api.models?.deleteAlias) {
            throw new Error('core.apiClient is missing models.deleteAlias');
        }
        const result = await api.models.deleteAlias(universalId);
        if (result === undefined) {
            throw new Error('core.apiClient.models.deleteAlias must return a value');
        }
        return result;
    }
});

export { modelActions, normalizeDownloadPayload, resolveStreamManager };
