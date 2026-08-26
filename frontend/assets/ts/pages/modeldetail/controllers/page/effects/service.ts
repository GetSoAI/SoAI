/* SoAI - Model detail page control layer effects service [frontend/assets/ts/pages/modeldetail/controllers/page/effects/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError, extractErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { MODEL_SNAPSHOT_CACHE, MODEL_STORAGE_PREFIX, PARAMETER_STORAGE_PREFIX, PARAMETER_SNAPSHOT_CACHE, modelDetailLogger, readSnapshot, writeSnapshot } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ModelDetailEffectsDependencies, ModelDetailEffectsHost, ParametersData } from '@pages/modeldetail/controllers/page/effects/types.ts';
import { extractModelDetailPayload } from '@pages/modeldetail/controllers/page/mappers.ts';
import { getModelDetailPluginName } from '@pages/modeldetail/controllers/page/state.ts';
import { setModelDetailPageState, updateModelDetailBackendDocumentationLink } from '@pages/modeldetail/controllers/page/view/service.ts';
import { fetchModelSnapshotFromCollection, fetchParametersViaWebSocketSnapshot } from '@pages/modeldetail/services/modelDetailSnapshotFetch.ts';
import { handleModelDetailMetricsUpdate, handleModelDetailPluginCollectionUpdate, handleModelDetailRealtimeModelUpdate } from '@pages/modeldetail/controllers/page/effects/events.ts';
import { ensureModelDetailRealtimeCollectionsReady } from '@pages/modeldetail/controllers/page/events.ts';
import { decodeModelDetailParameterPayload, serializeModelDetailParameterPayload } from '@pages/modeldetail/mappers/ModelDetailParameterPayloadDomain.ts';

const composeModelDetailEffects = (host: ModelDetailEffectsDependencies): ModelDetailEffectsHost => {
    const updateBackendDocumentationLink = async (options: { ensurePlugins?: boolean; plugins?: (JsonValue | null)[] | null } = {}): Promise<void> => {
        const resolved = await updateModelDetailBackendDocumentationLink(host.view, options);
        host.session.backendDocumentationUrl = resolved.backendDocumentationUrl;
        host.session.pluginSnapshot = resolved.pluginCollectionSnapshot;
        host.updateBackendDocButtonVisibility();
    };

    const effectsHost: ModelDetailEffectsHost = {
        state: {
            pageResources: host.pageResources,
            get isDestroyed(): boolean {
                return host.isDestroyed;
            },
            get modelId(): string | null {
                return host.session.modelId;
            },
            get model() {
                return host.session.model;
            },
            set model(value) {
                host.session.model = value;
                host.reconcileOpenAICapabilityState(value);
            },
            get parametersData() {
                return host.session.parameters;
            },
            set parametersData(value) {
                host.session.parameters = value;
            },
            get activeTab(): string {
                return host.session.activeTab;
            },
            get pluginCollectionSnapshot(): (JsonValue | null)[] {
                return host.session.pluginSnapshot;
            },
            set pluginCollectionSnapshot(value: (JsonValue | null)[]) {
                host.session.pluginSnapshot = value;
            },
            get currentMetrics(): JsonObject | null {
                return host.session.metrics;
            },
            set currentMetrics(value: JsonObject | null) {
                host.session.metrics = value;
            },
            streamManager: host.streamManager,
            parameterView: host.parameterView,
            ensureRealtimeCollectionsReady: () =>
                ensureModelDetailRealtimeCollectionsReady(host.session, {
                    pageResources: host.pageResources,
                    streaming: host.streaming,
                    handleModelUpdate: (value) => handleModelDetailRealtimeModelUpdate(effectsHost, value),
                    handleMetricsUpdate: (value) => handleModelDetailMetricsUpdate(effectsHost, value),
                    handlePluginCollectionUpdate: (value) => handleModelDetailPluginCollectionUpdate(effectsHost, value),
                    logRealtimeWarning: (message, error) => modelDetailLogger('warn', message, error)
                })
        },
        rendering: {
            runWithBoundary: (name, functionValue) => host.pageLifecycle.run(name, functionValue),
            setLoadError: (error) => host.setLoadError(error),
            setPageState: (state) => setModelDetailPageState(host.view, state),
            applyParametersPayload: (payload) => host.applyParametersPayload(payload),
            populateModelInfo: () => host.populateModelInfo(),
            renderParametersInterface: () => host.renderParametersInterface(),
            persistSnapshots: (modelSnapshot, parameterSnapshot): void => {
                persistModelDetailSnapshots(host.session.modelId, modelSnapshot, parameterSnapshot);
            },
            updateBackendDocumentationLink,
            updateTestPluginStatusDisplay: () => host.updateTestPluginStatusDisplay(),
            populateDetailCards: () => host.populateDetailCards(),
            setInfo: (id, value) => host.setInfo(id, value),
            getModelPluginName: (): string => getModelDetailPluginName(host.session.model),
            onModelDeleted: (): void => {
                host.feedback.show(i18n.t('modelDetail.notifications.modelDeleted'), 'info');
                const router = host.router;
                if (!router) {
                    throw new Error('ModelDetailPage requires router for navigation');
                }
                host.pageResources.setTimeout(() => router.navigate('models'), 400);
            }
        }
    };
    return effectsHost;
};
const isModelDetailSnapshotAbortError = (value: Error | JsonValue | null | undefined, isDestroyed: boolean): boolean => {
    return isDestroyed && isAbortError(value);
};
const isModelDetailNotFoundError = (value: Error | JsonValue | null | undefined): boolean => {
    const message = extractErrorMessage(value);
    return Boolean(message && message.includes('not found in collection'));
};
interface SnapshotMemoryCache<T> {
    get(key: string): T | null;
    set(key: string, value: T): void;
    delete(key: string): void;
}

const fetchModelDetailSnapshotData = async <T>(cache: SnapshotMemoryCache<T | null>, modelId: string, debugStartMessage: string, debugDoneMessage: string, emptyMessage: string, taskFunctionValue: () => Promise<T | null>, errorMessage: string, isDestroyed: boolean): Promise<T | null> => {
    const cached = cache.get(modelId);
    if (cached) {
        return cached;
    }
    errorHandler.debug('ModelDetailPage', debugStartMessage, { id: modelId });
    try {
        const data = await taskFunctionValue();
        if (!data) {
            throw new Error(emptyMessage);
        }
        cache.set(modelId, data);
        errorHandler.debug('ModelDetailPage', debugDoneMessage, { id: modelId });
        return data;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isModelDetailSnapshotAbortError(runtimeError, isDestroyed)) {
            if (isModelDetailNotFoundError(runtimeError)) {
                errorHandler.warn('ModelDetailPage', errorMessage, { id: modelId, error: runtimeError });
            } else {
                errorHandler.error('ModelDetailPage', errorMessage, { id: modelId, error: runtimeError });
            }
        }
        cache.delete(modelId);
        throw runtimeError;
    }
};
const fetchModelDetailSnapshot = async (host: ModelDetailEffectsHost): Promise<ModelRecord | null> => {
    if (!host.state.modelId) {
        throw new Error('ModelDetailPage requires a model identifier');
    }
    return fetchModelDetailSnapshotData(
        MODEL_SNAPSHOT_CACHE,
        host.state.modelId,
        'Fetching model from collection stream',
        'Model snapshot received from collection',
        'Model data unavailable',
        () =>
            fetchModelSnapshotFromCollection({
                modelId: host.state.modelId,
                streamManager: host.state.streamManager,
                extractModelPayload: (raw: JsonValue | null) => extractModelDetailPayload(host.state.modelId, raw)
            }),
        'Model snapshot request failed',
        host.state.isDestroyed
    );
};
const fetchModelDetailParametersViaWebSocket = async (host: ModelDetailEffectsHost): Promise<ParametersData> => {
    if (!host.state.modelId) {
        throw new Error('ModelDetailPage requires a model identifier');
    }
    return fetchParametersViaWebSocketSnapshot({ modelId: host.state.modelId, model: host.state.model });
};
const fetchModelDetailParametersSnapshot = async (host: ModelDetailEffectsHost): Promise<ParametersData | null> => {
    if (!host.state.modelId) {
        throw new Error('ModelDetailPage requires a model identifier');
    }
    return fetchModelDetailSnapshotData(PARAMETER_SNAPSHOT_CACHE, host.state.modelId, 'Fetching parameter snapshot (WebSocket)', 'Parameter snapshot received', 'Model parameters payload is unavailable', () => fetchModelDetailParametersViaWebSocket(host), 'Parameter snapshot request failed', host.state.isDestroyed);
};
const loadModelDetailData = async (host: ModelDetailEffectsHost): Promise<void> => {
    await host.rendering.runWithBoundary('modelDetail:loadModelDetails', async (): Promise<void> => {
        try {
            const cachedModel = host.state.modelId ? readSnapshot(MODEL_STORAGE_PREFIX, host.state.modelId) : null;
            const cachedParameters = host.state.modelId ? readCachedModelDetailParameters(host.state.modelId) : null;
            if (cachedModel && cachedParameters && isObject(cachedModel)) {
                host.rendering.setLoadError(null);
                host.state.model = cachedModel;
                host.state.parameterView.setModel(host.state.model);
                host.state.parametersData = cachedParameters;
                host.rendering.applyParametersPayload(cachedParameters);
                host.rendering.populateModelInfo();
                if (host.state.activeTab === 'parameters') {
                    host.rendering.renderParametersInterface();
                }
                host.rendering.setPageState('ready');
                terminateHandledPromise(refreshModelDetailSnapshots(host));
                return;
            }
            await host.state.ensureRealtimeCollectionsReady();
            const modelSnapshot = await fetchModelDetailSnapshot(host);
            if (!isObject(modelSnapshot)) {
                throw new Error('Model snapshot is unavailable');
            }
            host.state.model = modelSnapshot;
            errorHandler.info('ModelDetailPage', 'Model snapshot loaded', { id: host.state.modelId });
            host.state.parameterView.setModel(host.state.model);
            await host.rendering.updateBackendDocumentationLink();
            host.rendering.populateModelInfo();
            const parametersSnapshot = await fetchModelDetailParametersSnapshot(host);
            if (!parametersSnapshot) {
                throw new Error('Model parameters payload is unavailable');
            }
            host.state.parametersData = parametersSnapshot;
            host.rendering.applyParametersPayload(parametersSnapshot);
            errorHandler.info('ModelDetailPage', 'Model parameters loaded', { id: host.state.modelId });
            host.rendering.persistSnapshots(host.state.model, host.state.parametersData);
            if (host.state.activeTab === 'parameters') {
                host.rendering.renderParametersInterface();
            }
            host.rendering.setLoadError(null);
            host.rendering.setPageState('ready');
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isModelDetailSnapshotAbortError(runtimeError, host.state.isDestroyed)) {
                host.rendering.setLoadError(runtimeError);
                host.rendering.setPageState('error');
                if (!isModelDetailNotFoundError(runtimeError)) {
                    errorHandler.handleError(runtimeError, { context: 'ModelDetailPage.loadModelDetails' });
                }
            }
        }
    });
};
const refreshModelDetailSnapshots = async (host: ModelDetailEffectsHost): Promise<void> => {
    try {
        await host.state.ensureRealtimeCollectionsReady();
        const modelSnapshot = await fetchModelDetailSnapshot(host);
        if (!isObject(modelSnapshot)) {
            throw new Error('Model snapshot is unavailable');
        }
        const parameterSnapshot = await fetchModelDetailParametersSnapshot(host);
        if (!parameterSnapshot) {
            throw new Error('Model parameters payload is unavailable');
        }
        host.state.model = modelSnapshot;
        host.state.parameterView.setModel(host.state.model);
        host.state.parametersData = parameterSnapshot;
        host.rendering.applyParametersPayload(parameterSnapshot);
        host.rendering.persistSnapshots(modelSnapshot, parameterSnapshot);
        host.rendering.populateModelInfo();
        if (host.state.activeTab === 'parameters') {
            host.rendering.renderParametersInterface();
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug('ModelDetailPage', 'Snapshot refresh failed', runtimeError);
    }
};
const persistModelDetailSnapshots = (modelId: string | null, model: ModelDetailEffectsHost['state']['model'], parameters: ModelDetailEffectsHost['state']['parametersData']): void => {
    if (!modelId) {
        return;
    }
    if (model) {
        writeSnapshot(MODEL_STORAGE_PREFIX, modelId, toJsonCompatibleValue(model));
    }
    if (parameters) {
        writeSnapshot(PARAMETER_STORAGE_PREFIX, modelId, serializeModelDetailParameterPayload(parameters));
    }
};

const readCachedModelDetailParameters = (modelId: string): ParametersData | null => {
    const snapshot = readSnapshot(PARAMETER_STORAGE_PREFIX, modelId);
    if (snapshot === null) return null;
    try {
        return decodeModelDetailParameterPayload(snapshot);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ModelDetailPage', 'Discarding invalid cached parameter snapshot', { id: modelId, error: runtimeError });
        return null;
    }
};

export { composeModelDetailEffects, fetchModelDetailParametersSnapshot, fetchModelDetailParametersViaWebSocket, fetchModelDetailSnapshot, isModelDetailNotFoundError, isModelDetailSnapshotAbortError, loadModelDetailData, persistModelDetailSnapshots, readCachedModelDetailParameters, refreshModelDetailSnapshots };
export type { ModelDetailEffectsHost };
