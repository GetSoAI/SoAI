/* SoAI - Model detail page control layer action effects [frontend/assets/ts/pages/modeldetail/controllers/page/actionEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { OpenAICapabilityOverrideCategory } from '@core/openai/capabilityCategories.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { hasOpenAICapabilityOverrideChanges, saveOpenAICapabilityOverrideState, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { Parameter } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { sanitizeParameterValue } from '@pages/modeldetail/mappers/parameterValueNormalization.ts';
import type { ModelDetailParametersData } from '@pages/modeldetail/types.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';

type ParametersData = ModelDetailParametersData;

interface ModelDetailParameterStatePort {
    getParameter(key: string): Parameter | null | undefined;
    commit(): void;
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
    updateOpenAICapabilityOverride(modelId: string, payload: { category: OpenAICapabilityOverrideCategory; token: string; enabled: boolean }): Promise<SuccessfulMutationResponse>;
    resetOpenAICapabilityOverrides(modelId: string): Promise<SuccessfulMutationResponse>;
}

interface ModelDetailActionsHost extends PageResourcesOwnerHost, PageFeedbackOwnerHost {
    model: ModelRecord | null;
    parametersData: ParametersData | null;
    parameterState: ModelDetailParameterStatePort;
    parameterView: ModelDetailParameterViewPort;
    getOpenAICapabilityState: () => OpenAICapabilityOverrideState | null;
    applySavedOpenAICapabilityModel: (model: ModelRecord) => void;
    populateDetailCards: () => void;
    notifySaveChanged: () => void;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    requireModelId: () => string;
    refreshModelsCollection: () => Promise<void>;
    api: { models: ModelDetailModelApiPort };
    isVirtualModel: () => boolean;
    applyParametersPayload: (payload: ParametersData) => void;
    setParametersData: (payload: ParametersData) => void;
    fetchParametersSnapshot: () => Promise<ParametersData | null>;
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
    applyParametersPayload: ModelDetailActionsHost['applyParametersPayload'];
    populateDetailCards: ModelDetailActionsHost['populateDetailCards'];
    notifySaveChanged: ModelDetailActionsHost['notifySaveChanged'];
    fetchParametersSnapshot: ModelDetailActionsHost['fetchParametersSnapshot'];
}

const composeModelDetailActions = (host: ModelDetailActionsDependencies): ModelDetailActionsHost => {
    return {
        get model(): ModelRecord | null {
            return host.session.model;
        },
        get parametersData(): ParametersData | null {
            return host.session.parameters;
        },
        parameterState: host.parameterState,
        parameterView: host.parameterView,
        runWithBoundary: <T>(name: string, functionValue: () => Promise<T>): Promise<T> => host.pageLifecycle.run(name, functionValue),
        requireModelId: (): string => host.requireModelId(),
        refreshModelsCollection: async (): Promise<void> => {
            await host.streamManager.resources.refresh(MODELS, { throwOnError: true });
        },
        pageResources: host.pageResources,
        feedback: host.feedback,
        api: host.api,
        isVirtualModel: (): boolean => host.isVirtualModel(),
        getOpenAICapabilityState: (): OpenAICapabilityOverrideState | null => host.getOpenAICapabilityState(),
        applySavedOpenAICapabilityModel: (model: ModelRecord): void => host.applySavedOpenAICapabilityModel(model),
        applyParametersPayload: (payload: ParametersData): void => host.applyParametersPayload(payload),
        populateDetailCards: (): void => host.populateDetailCards(),
        notifySaveChanged: (): void => host.notifySaveChanged(),
        setParametersData: (payload: ParametersData): void => {
            host.session.parameters = payload;
        },
        fetchParametersSnapshot: (): Promise<ParametersData | null> => host.fetchParametersSnapshot()
    };
};

const loadModelDetailParametersData = async (host: ModelDetailActionsHost): Promise<void> => {
    return host.runWithBoundary('modelDetail:loadParametersData', async () => {
        host.applyParametersPayload({});
        if (host.isVirtualModel()) {
            if (!isArray(host.model?.models)) {
                throw new TypeError('virtual model models must be an array');
            }
            const virtualPayload: ParametersData = {
                type: 'virtual',
                ...(isString(host.model?.strategy) ? { strategy: host.model.strategy } : {}),
                models: host.model.models
            };
            host.setParametersData(virtualPayload);
            return;
        }
        const snapshot = await host.fetchParametersSnapshot();
        if (!snapshot) {
            throw new Error('Model parameters payload is unavailable');
        }
        host.applyParametersPayload(snapshot);
        host.setParametersData(snapshot);
    });
};

const resetAllModelDetailParameters = async (host: ModelDetailActionsHost): Promise<void> => {
    if (
        !(await requireDialogsService().showConfirmation({
            title: i18n.t('modelDetail.confirmations.resetParameters'),
            message: i18n.t('modelDetail.confirmations.resetParametersMessage'),
            confirmText: i18n.t('modelDetail.confirmations.resetParametersConfirm'),
            cancelText: i18n.t('modelDetail.confirmations.cancel')
        }))
    ) {
        return;
    }
    host.parameterView.resetAllParameters();
};

const saveModelDetailParameters = async (host: ModelDetailActionsHost): Promise<void> => {
    return host.runWithBoundary('modelDetail:saveParameters', async () => {
        const modifiedKeys = host.parameterView.getModifiedParameterKeys();
        if (!modifiedKeys.length) {
            host.feedback.show(i18n.t('modelDetail.notifications.noModifiedParams'), 'info');
            return;
        }
        const payload = modifiedKeys.reduce((accumulator: Record<string, JsonValue>, key: string) => {
            const parameter = host.parameterState.getParameter(key);
            if (parameter) {
                accumulator[key] = sanitizeParameterValue(parameter, parameter.currentValue) ?? null;
            }
            return accumulator;
        }, {});
        await host.api.models.updateParameters(host.requireModelId(), toJsonCompatibleValue(payload));
        host.feedback.show(i18n.t('modelDetail.notifications.paramsSaved'), 'success');
        host.parameterState.commit();
        host.parameterView.refreshModificationState();
    });
};

const saveModelDetailOpenAICapabilities = async (host: ModelDetailActionsHost): Promise<void> => {
    await host.runWithBoundary('modelDetail:saveOpenAICapabilities', async () => {
        const state = host.getOpenAICapabilityState();
        if (!host.model || !state || !hasOpenAICapabilityOverrideChanges(state)) {
            return;
        }
        const updatedModel = await saveOpenAICapabilityOverrideState({
            api: host.api.models,
            model: host.model,
            state
        });
        host.applySavedOpenAICapabilityModel(updatedModel);
        host.populateDetailCards();
        host.feedback.show(i18n.t('modelDetail.notifications.capabilitiesUpdated'), 'success');
        try {
            await host.refreshModelsCollection();
            host.populateDetailCards();
        } catch (error) {
            errorHandler.handleError(ensureError(error), { context: 'ModelDetailPage.saveOpenAICapabilities.refreshModelsCollection' });
        }
    });
};

export { composeModelDetailActions, loadModelDetailParametersData, resetAllModelDetailParameters, saveModelDetailOpenAICapabilities, saveModelDetailParameters };
export type { ModelDetailActionsDependencies, ModelDetailActionsHost };
