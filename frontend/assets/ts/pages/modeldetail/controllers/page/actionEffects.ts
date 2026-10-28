/* SoAI - Model detail page control layer action effects [frontend/assets/ts/pages/modeldetail/controllers/page/actionEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { OpenAICapabilityOverrideReplaceRequest } from '@core/openai/capabilityCategories.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { deepClone, toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { discardOpenAICapabilityOverrideChanges, hasOpenAICapabilityOverrideChanges, isOpenAICapabilityOverrideConflict, saveOpenAICapabilityOverrideState, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { Parameter } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { sanitizeParameterValue } from '@pages/modeldetail/mappers/parameterValueNormalization.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { ModelDetailParameterAuthority } from '@pages/modeldetail/state/ModelDetailParameterAuthorityState.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';

interface ModelDetailParameterStatePort {
    getParameter(key: string): Parameter | null | undefined;
    commit(submittedValues: Record<string, JsonValue>): void;
}

interface ModelDetailParameterViewPort {
    refreshModificationState(): void;
    resetAllParameters(): void;
    getModifiedParameterKeys(): string[];
    hasParameterChanges(): boolean;
    areParametersValid(): boolean;
}

interface ModelDetailModelApiPort {
    updateParameters(modelId: string, payload: JsonValue): Promise<SuccessfulMutationResponse>;
    updateEnabled(modelId: string, payload: { enabled: boolean }): Promise<SuccessfulMutationResponse>;
    replaceOpenAICapabilityOverrides(modelId: string, payload: OpenAICapabilityOverrideReplaceRequest): Promise<SuccessfulMutationResponse>;
}

interface ModelDetailParameterSnapshotPort {
    parameterAuthority: ModelDetailParameterAuthority;
    beginParameterSave: () => void;
    finishParameterSave: () => void;
    retryParameters: () => void;
    discardParameterChanges: () => void;
}

interface ModelDetailActionsHost extends PageResourcesOwnerHost, PageFeedbackOwnerHost, ModelDetailParameterSnapshotPort {
    model: ModelRecord | null;
    parameterState: ModelDetailParameterStatePort;
    parameterView: ModelDetailParameterViewPort;
    getOpenAICapabilityState: () => OpenAICapabilityOverrideState | null;
    applySavedOpenAICapabilityModel: (model: ModelRecord) => void;
    populateDetailCards: () => void;
    notifySaveChanged: () => void;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    requireModelId: () => string;
    getPageSignal: () => AbortSignal | null;
    refreshModelsCollection: () => Promise<void>;
    api: { models: ModelDetailModelApiPort };
    isVirtualModel: () => boolean;
}

interface ModelDetailActionsDependencies extends PageResourcesOwnerHost, PageFeedbackOwnerHost, PageLifecycleOwnerHost {
    session: ModelDetailSession;
    parameterState: ModelDetailActionsHost['parameterState'];
    parameterView: ModelDetailActionsHost['parameterView'];
    requireModelId: ModelDetailActionsHost['requireModelId'];
    streamManager: StreamRuntimeOwners;
    api: ModelDetailActionsHost['api'];
    isVirtualModel: ModelDetailActionsHost['isVirtualModel'];
    getOpenAICapabilityState: ModelDetailActionsHost['getOpenAICapabilityState'];
    applySavedOpenAICapabilityModel: ModelDetailActionsHost['applySavedOpenAICapabilityModel'];
    populateDetailCards: ModelDetailActionsHost['populateDetailCards'];
    notifySaveChanged: ModelDetailActionsHost['notifySaveChanged'];
    parameterSnapshots: Omit<ModelDetailParameterSnapshotPort, 'parameterAuthority'>;
}

const composeModelDetailActions = (host: ModelDetailActionsDependencies): ModelDetailActionsHost => {
    return {
        get model(): ModelRecord | null {
            return host.session.model;
        },
        set model(model: ModelRecord | null) {
            host.session.model = model;
        },
        parameterState: host.parameterState,
        parameterView: host.parameterView,
        runWithBoundary: <T>(name: string, functionValue: () => Promise<T>): Promise<T> => host.pageLifecycle.run(name, functionValue),
        requireModelId: (): string => host.requireModelId(),
        getPageSignal: (): AbortSignal | null => host.pageLifecycle.signal(),
        refreshModelsCollection: async (): Promise<void> => {
            await host.streamManager.resources.refresh(MODELS, { throwOnError: true });
        },
        pageResources: host.pageResources,
        feedback: host.feedback,
        api: host.api,
        isVirtualModel: (): boolean => host.isVirtualModel(),
        getOpenAICapabilityState: (): OpenAICapabilityOverrideState | null => host.getOpenAICapabilityState(),
        applySavedOpenAICapabilityModel: (model: ModelRecord): void => host.applySavedOpenAICapabilityModel(model),
        populateDetailCards: (): void => host.populateDetailCards(),
        notifySaveChanged: (): void => host.notifySaveChanged(),
        get parameterAuthority(): ModelDetailParameterAuthority {
            return host.session.parameterAuthority;
        },
        ...host.parameterSnapshots
    };
};

const saveModelDetailParameters = async (host: ModelDetailActionsHost): Promise<void> => {
    return host.runWithBoundary('modelDetail:saveParameters', async () => {
        const modifiedKeys = host.parameterView.getModifiedParameterKeys();
        if (!modifiedKeys.length) {
            host.feedback.show(i18n.t('modelDetail.notifications.noModifiedParams'), 'info');
            return;
        }
        if (!host.parameterAuthority.canSubmit) {
            host.feedback.show(i18n.t('modelDetail.parameterAvailability.saveBlocked'), 'warning');
            return;
        }
        const signal = host.getPageSignal();
        const modelId = host.requireModelId();
        const submittedValues: Record<string, JsonValue> = {};
        const payload = modifiedKeys.reduce((accumulator: Record<string, JsonValue>, key: string) => {
            const parameter = host.parameterState.getParameter(key);
            if (parameter) {
                submittedValues[key] = deepClone(parameter.currentValue ?? null);
                accumulator[key] = sanitizeParameterValue(parameter, parameter.currentValue) ?? null;
            }
            return accumulator;
        }, {});
        const isCurrentSession = (): boolean => signal?.aborted !== true && host.model?.universalId === modelId;
        host.beginParameterSave();
        try {
            await host.api.models.updateParameters(modelId, toJsonCompatibleValue(payload));
        } catch (error) {
            if (isCurrentSession()) host.finishParameterSave();
            throw ensureError(error);
        }
        if (!isCurrentSession()) return;
        host.feedback.show(i18n.t('modelDetail.notifications.paramsSaved'), 'success');
        host.parameterState.commit(submittedValues);
        host.parameterView.refreshModificationState();
        host.finishParameterSave();
    });
};

const saveModelDetailOpenAICapabilities = async (host: ModelDetailActionsHost): Promise<void> => {
    await host.runWithBoundary('modelDetail:saveOpenAICapabilities', async () => {
        const state = host.getOpenAICapabilityState();
        const model = host.model;
        if (!model || !state || !hasOpenAICapabilityOverrideChanges(state)) {
            return;
        }
        const signal = host.getPageSignal();
        const isCurrent = (): boolean => signal?.aborted !== true && host.getOpenAICapabilityState() === state;
        let updatedModel: ModelRecord;
        try {
            updatedModel = await saveOpenAICapabilityOverrideState({ api: host.api.models, model, state });
        } catch (error) {
            const normalizedError = ensureError(error);
            if (!isOpenAICapabilityOverrideConflict(normalizedError)) {
                throw normalizedError;
            }
            errorHandler.debug('ModelDetailPage', 'Capability override save conflicted with a newer model revision', { modelId: model.id });
            if (!isCurrent()) {
                return;
            }
            discardOpenAICapabilityOverrideChanges(state);
            host.feedback.show(i18n.t('modelDetail.notifications.capabilitiesConflict'), 'error');
            await host.refreshModelsCollection();
            if (signal?.aborted || host.model?.id !== model.id) return;
            host.populateDetailCards();
            host.notifySaveChanged();
            return;
        }
        if (!isCurrent()) {
            return;
        }
        host.applySavedOpenAICapabilityModel(updatedModel);
        host.populateDetailCards();
        host.feedback.show(i18n.t('modelDetail.notifications.capabilitiesUpdated'), 'success');
        try {
            await host.refreshModelsCollection();
            if (signal?.aborted || host.model?.id !== model.id) return;
            host.populateDetailCards();
        } catch (error) {
            errorHandler.handleError(ensureError(error), { context: 'ModelDetailPage.saveOpenAICapabilities.refreshModelsCollection' });
        }
    });
};

export { composeModelDetailActions, saveModelDetailOpenAICapabilities, saveModelDetailParameters };
export type { ModelDetailActionsDependencies, ModelDetailActionsHost };
