/* SoAI - Model detail page control layer effects events [frontend/assets/ts/pages/modeldetail/controllers/page/effects/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { unwrap } from '@core/realtime/streammanager/resources/normalizers.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { ModelDetailEffectsHost } from '@pages/modeldetail/controllers/page/effects/types.ts';
import { extractModelDetailPayload, isModelDetailStillPresent } from '@pages/modeldetail/controllers/page/mappers.ts';
import { applyModelDetailMetricsUpdate } from '@pages/modeldetail/widgets/modelDetailMetrics.ts';

const modelDetailEffectsLogger = createModuleLogger('ModelDetailPage', { defaultLevel: 'warn' });

const handleModelDetailPluginCollectionUpdate = (host: ModelDetailEffectsHost, payload: JsonValue | null): void => {
    const plugins: (JsonValue | null)[] = isArray(payload) ? Array.from(payload) : [];
    host.state.pluginCollectionSnapshot = plugins;
    if (plugins.length > 0) {
        terminateHandledPromise(host.rendering.updateBackendDocumentationLink({ ensurePlugins: false, plugins }));
    }

    const pluginName = host.rendering.getModelPluginName();
    if (pluginName && host.state.pluginCollectionSnapshot.length > 0) {
        const matchingPlugin = host.state.pluginCollectionSnapshot.find((entry: JsonValue): boolean => {
            if (!isObject(entry)) {
                return false;
            }
            const expected = pluginName.toLowerCase();
            const name = entry['name'];
            return isString(name) && name.toLowerCase() === expected;
        });
        if (matchingPlugin && isObject(matchingPlugin)) {
            const nextState = matchingPlugin['state'];
            if (isString(nextState) && host.state.model) {
                host.state.model = { ...host.state.model, pluginStatus: nextState };
                host.rendering.updateTestPluginStatusDisplay();
            }
        }
    }

    host.rendering.populateDetailCards();
};

const handleModelDetailMetricsUpdate = (host: ModelDetailEffectsHost, payload: JsonValue | null): void => {
    applyModelDetailMetricsUpdate(
        {
            unwrapPayload: (raw: JsonValue | null): JsonValue | null => unwrap(raw),
            setCurrentMetrics: (raw): void => {
                host.state.currentMetrics = raw;
            },
            getModel: () => host.state.model,
            setInfo: (id: string, value: JsonValue | null | undefined): void => host.rendering.setInfo(id, value),
            getPluginKey: (): string => host.rendering.getModelPluginName(),
            updateTestPluginStatusDisplay: (): void => host.rendering.updateTestPluginStatusDisplay()
        },
        payload
    );
};

const applyCurrentModelDetailMetrics = (host: ModelDetailEffectsHost): void => {
    if (host.state.currentMetrics) {
        handleModelDetailMetricsUpdate(host, host.state.currentMetrics);
    }
};

const handleModelDetailRealtimeModelUpdate = (host: ModelDetailEffectsHost, payload: JsonValue | null): void => {
    const updatedModel = extractModelDetailPayload(host.state.modelId, payload);
    if (updatedModel) {
        if (!host.state.model) {
            return;
        }
        const providerCandidate = updatedModel['provider'];
        const provider = isString(providerCandidate) && providerCandidate ? providerCandidate : host.state.model.provider;
        host.state.model = provider === undefined ? { ...host.state.model, ...updatedModel } : { ...host.state.model, ...updatedModel, provider };
        host.state.parameterView.setModel(host.state.model);
        host.rendering.populateModelInfo();
        applyCurrentModelDetailMetrics(host);
        terminateHandledPromise(host.rendering.updateBackendDocumentationLink({ ensurePlugins: false }));
        host.rendering.updateTestPluginStatusDisplay();
        host.rendering.populateDetailCards();
        return;
    }

    if (host.state.model && !isModelDetailStillPresent(host.state.modelId, payload)) {
        modelDetailEffectsLogger('warn', 'Model was removed from stream payload');
        host.rendering.onModelDeleted();
    }
};

export { handleModelDetailMetricsUpdate, handleModelDetailPluginCollectionUpdate, handleModelDetailRealtimeModelUpdate };
