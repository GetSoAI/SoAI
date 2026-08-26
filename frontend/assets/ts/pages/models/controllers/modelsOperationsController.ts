/* SoAI - Models page operations controller [frontend/assets/ts/pages/models/controllers/modelsOperationsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stopPluginActionPath } from '@core/api/endpoints/uiPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import type { StreamActionHandle, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import { resolveTaskOperationFailureText } from '@core/tasks/operationText.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { ACTIVE_MODEL_STATUSES } from '@pages/models/contracts/ModelPageSupport.ts';
import { resolveModelEnabledToggleTarget, type ModelEnabledToggleTarget } from '@pages/models/controllers/modelsModelProperties.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';

interface StopModelDependencies {
    runWithBoundary: <T>(op: string, task: () => Promise<T> | T) => Promise<T>;
    showNotification: (message: string, type: 'success' | 'warning' | 'info' | 'error') => void;
    getModelPlugin: (model: ModelRecord) => string;
    getModelStatus: (model: ModelRecord) => string;
    getStreamTracker: (scope: string) => StreamHandleTrackerContract;
    runPageTask: <T>(taskName: string, task: () => Promise<T>, options: { displayName: string; rethrow: boolean }) => Promise<T | null>;
    startTaskAction: (path: string, initialize: { method: string }) => Promise<StreamActionHandle>;
}

interface DeleteModelDependencies {
    getModelPlugin: (model: ResourceItem | null | undefined) => string;
    isExternalProviderModel: (model: ResourceItem | null | undefined) => boolean;
    getCollectionItem: (identifier: string) => ResourceItem | null;
    deleteVirtualModel: (vmName: string) => Promise<void>;
    executeItemDeletion: (config: { identifier: string; confirmTitle: string; confirmMessage: string; confirmButton: string; getStream: () => Promise<StreamActionHandle>; gridId: string; findCard?: (grid: HTMLElement | null, id: string) => HTMLElement | null; pendingClass: string; successMessage: string }) => Promise<void>;
    modelActionsDelete: (identifier: string) => Promise<StreamActionHandle>;
    gridId: string;
    findCard: (grid: HTMLElement | null, id: string) => HTMLElement | null;
}

interface ToggleModelEnabledDependencies {
    runWithBoundary: <T>(op: string, task: () => Promise<T> | T) => Promise<T>;
    updateEnabled: (modelId: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>;
    updateVirtualEnabled: (vmName: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>;
    getCurrentModel: (cardId: string) => ModelRecord | null;
    commitEnabledState: (cardId: string, enabled: boolean) => ModelRecord | null;
    setPendingToggleTarget: (targetKey: string, enabled: boolean) => void;
    clearPendingToggleTarget: (targetKey: string) => void;
    rerenderModel: (cardId: string) => void;
    showNotification: (message: string, type: 'success' | 'warning' | 'info' | 'error') => void;
    updateStats: () => void;
}

interface ModelsOperationsController {
    stopModel: (model: ModelRecord) => Promise<void>;
    deleteModel: (identifier: string | number) => Promise<void>;
    toggleModelEnabled: (model: ModelRecord, event?: Event) => Promise<void>;
}

const createModelsDeleteController = (dependencies: DeleteModelDependencies): ((identifier: string | number) => Promise<void>) => {
    return async (identifier: string | number): Promise<void> => {
        const universalId = String(identifier);
        const modelRaw = dependencies.getCollectionItem(universalId);
        const model = isObject(modelRaw) ? modelRaw : null;
        const getModelProp = (key: string): string | undefined => {
            const value = model?.[key];
            return typeof value === 'string' ? value : undefined;
        };
        const modelName = getModelProp('display_name') ?? getModelProp('alias') ?? getModelProp('name') ?? getModelProp('id') ?? universalId;

        if (model?.['type'] === 'virtual') {
            const vmName = getModelProp('name') || getModelProp('id') || modelName;
            await dependencies.deleteVirtualModel(vmName);
            return;
        }
        if (model && dependencies.isExternalProviderModel(model)) {
            await requireDialogsService().showConfirmation({
                title: i18n.t('models.notifications.cannotDeleteExternal'),
                message: i18n.t('models.notifications.cannotDeleteExternalMessage', { model: modelName }),
                description: i18n.t('models.notifications.cannotDeleteExternalDescription', {
                    plugin: dependencies.getModelPlugin(model)
                }),
                confirmText: i18n.t('common.ok'),
                variant: 'info',
                icon: 'info'
            });
            return;
        }

        await dependencies.executeItemDeletion({
            identifier: universalId,
            confirmTitle: i18n.t('models.confirmations.deleteModel'),
            confirmMessage: i18n.t('models.confirmations.deleteModelMessage', { model: modelName }),
            confirmButton: i18n.t('models.confirmations.deleteModelButton'),
            getStream: () => dependencies.modelActionsDelete(String(universalId)),
            gridId: dependencies.gridId,
            findCard: dependencies.findCard,
            pendingClass: 'pending-delete',
            successMessage: i18n.t('models.notifications.deleteSuccess', { model: modelName })
        });
    };
};

const createModelsOperationsController = (dependencies: { stop: StopModelDependencies; del: DeleteModelDependencies; enabled: ToggleModelEnabledDependencies }): ModelsOperationsController => {
    const activeEnabledToggles = new Set<string>();
    const stopModel = async (model: ModelRecord): Promise<void> => {
        return dependencies.stop.runWithBoundary('models:stopModel', async () => {
            const pluginName = dependencies.stop.getModelPlugin(model);
            if (!pluginName) return;
            if (!ACTIVE_MODEL_STATUSES.includes(dependencies.stop.getModelStatus(model))) {
                dependencies.stop.showNotification(i18n.t('models.notifications.modelNotStoppable'), 'warning');
                return;
            }
            const tracker = dependencies.stop.getStreamTracker('models.actions');
            const result = await dependencies.stop.runPageTask(
                `models.stop.${pluginName}`,
                async () => {
                    const stream = await dependencies.stop.startTaskAction(stopPluginActionPath(pluginName), { method: 'POST' });
                    const settled = await settleTrackedTaskStream({
                        tracker,
                        stream,
                        keyPrefix: `models.stop.${pluginName}`,
                        keySeparator: '.',
                        failMessage: resolveTaskOperationFailureText('pluginStop')
                    });
                    if (settled.cancelled || settled.detached) {
                        return { cancelled: settled.cancelled, detached: settled.detached };
                    }
                    if (!settled.record) throw new Error('Invalid or missing response record');
                    return settled.record;
                },
                {
                    displayName: i18n.t('models.notifications.pluginStopInProgress', { plugin: pluginName }),
                    rethrow: false
                }
            );
            if (!result || !isObject(result) || result['cancelled'] === true || result['detached'] === true) return;
            dependencies.stop.showNotification(i18n.t('models.notifications.pluginStopSuccess', { plugin: pluginName }), 'success');
        });
    };

    const deleteModel = createModelsDeleteController(dependencies.del);

    const persistEnabledState = (target: ModelEnabledToggleTarget, enabled: boolean): Promise<SuccessfulMutationResponse> => {
        if (target.targetType === 'virtual') {
            return dependencies.enabled.updateVirtualEnabled(target.requestId, { enabled });
        }
        return dependencies.enabled.updateEnabled(target.requestId, { enabled });
    };

    const toggleModelEnabled = async (model: ModelRecord, event?: Event): Promise<void> => {
        event?.preventDefault();
        event?.stopPropagation();
        return dependencies.enabled.runWithBoundary('models:toggleModelEnabled', async () => {
            const clickedTarget = resolveModelEnabledToggleTarget(model);
            if (!clickedTarget) return;
            const currentModel = dependencies.enabled.getCurrentModel(clickedTarget.cardId) ?? model;
            const target = resolveModelEnabledToggleTarget(currentModel) ?? clickedTarget;
            if (activeEnabledToggles.has(target.targetKey)) return;
            activeEnabledToggles.add(target.targetKey);
            const enabled = currentModel.isEnabled === false;
            const isDisable = !enabled;
            dependencies.enabled.setPendingToggleTarget(target.targetKey, enabled);
            dependencies.enabled.rerenderModel(target.cardId);
            try {
                await persistEnabledState(target, enabled);
                dependencies.enabled.clearPendingToggleTarget(target.targetKey);
                dependencies.enabled.commitEnabledState(target.cardId, enabled);
                dependencies.enabled.rerenderModel(target.cardId);
                dependencies.enabled.updateStats();
                dependencies.enabled.showNotification(isDisable ? i18n.t('models.notifications.modelDisabled') : i18n.t('models.notifications.modelEnabled'), isDisable ? 'warning' : 'success');
            } catch (error) {
                dependencies.enabled.clearPendingToggleTarget(target.targetKey);
                dependencies.enabled.rerenderModel(target.cardId);
                dependencies.enabled.updateStats();
                throw error;
            } finally {
                activeEnabledToggles.delete(target.targetKey);
            }
        });
    };

    return { stopModel, deleteModel, toggleModelEnabled };
};

export { createModelsDeleteController, createModelsOperationsController };
export type { ModelsOperationsController, StopModelDependencies, DeleteModelDependencies, ToggleModelEnabledDependencies };
