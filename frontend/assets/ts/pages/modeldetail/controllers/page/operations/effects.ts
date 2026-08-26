/* SoAI - Model detail page control layer operations effects [frontend/assets/ts/pages/modeldetail/controllers/page/operations/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StreamFinishedValue } from '@core/routing/pages/pagetypes/stream/types.ts';
import { modelPath, stopPluginActionPath } from '@core/api/endpoints/uiPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createTaskFailureError } from '@core/operationErrorNotifier.ts';
import { isCancelledTaskStatus } from '@core/tasks/operationPayloads.ts';
import { resolveTaskOperationFailureText } from '@core/tasks/operationText.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import { isBoolean, isNumber, isObject, isString } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isStreamHandle } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ModelDetailOperationsHost } from '@pages/modeldetail/controllers/page/operations/types.ts';
import { clearModelDetailDeleteProgressState, setModelDetailDeleteBusy, updateModelDetailDeleteProgress } from '@pages/modeldetail/controllers/page/operations/view.ts';

const buildModelApiPath = (modelId: string, sub = ''): string => {
    const base = modelPath(modelId);
    return sub ? (sub.startsWith('/') ? base + sub : `${base}/${sub}`) : base;
};

const stopModelDetailPlugin = async (host: ModelDetailOperationsHost): Promise<void> => {
    return host.runWithBoundary('modelDetail:stopPlugin', async () => {
        if (!host.model?.plugin) {
            return;
        }
        const pluginName = host.model.plugin;
        if (host.getPluginStatus() === 'PERSISTENT_READY') {
            host.feedback.show(i18n.t('modelDetail.notifications.persistentPlugin'), 'warning');
            return;
        }
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('modelDetail.confirmations.stopPlugin'),
            message: i18n.t('modelDetail.confirmations.stopPluginMessage', { plugin: pluginName })
        });
        if (!confirmed) {
            return;
        }
        const tracker = host.getStreamTracker('modelDetail.actions');
        const result = await host.runPageTask(
            'modelDetail.stopPlugin',
            async () => {
                const started = await host.startTaskAction(stopPluginActionPath(pluginName), { method: 'POST' });
                if (!isStreamHandle(started)) {
                    throw new Error('Failed to start stop task');
                }
                if (!started.abort) {
                    throw new Error('Stop task stream is missing abort()');
                }
                const settled = await settleTrackedTaskStream({
                    tracker,
                    stream: {
                        abort: started.abort,
                        finished: started.finished
                    },
                    keyPrefix: `model-detail-stop-${pluginName}`,
                    failMessage: resolveTaskOperationFailureText('pluginStop')
                });
                if (settled.cancelled || settled.detached) {
                    return { cancelled: settled.cancelled, detached: settled.detached };
                }
                if (!settled.record) {
                    throw new Error('Plugin stop task did not return a response record');
                }
                return settled.record;
            },
            {
                displayName: i18n.t('modelDetail.notifications.pluginStopInProgress', { plugin: pluginName }),
                rethrow: false
            }
        );
        if (!result || !isObject(result) || result['cancelled'] === true || result['detached'] === true) {
            return;
        }
        host.feedback.show(i18n.t('modelDetail.notifications.pluginStopped', { plugin: pluginName }), 'success');
    });
};

const deleteModelDetailModel = async (host: ModelDetailOperationsHost): Promise<void> => {
    return host.runWithBoundary('modelDetail:deleteModel', async () => {
        if (host.activeDeletionStream) {
            host.feedback.show(i18n.t('modelDetail.notifications.deletionInProgress'), 'warning');
            return;
        }
        const displayName = host.getModelDisplayName() || i18n.t('modelDetail.notifications.thisModel');
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('modelDetail.confirmations.deleteModel'),
            message: i18n.t('modelDetail.confirmations.deleteModelMessage', { model: displayName }),
            confirmText: i18n.t('modelDetail.confirmations.deleteModelConfirm'),
            cancelText: i18n.t('modelDetail.confirmations.cancel')
        });
        if (!confirmed) {
            return;
        }
        if (host.isVirtualModel()) {
            const modelName = toTrimmedString(host.model?.name);
            if (!modelName) {
                throw new Error('ModelDetailPage virtual model deletion requires model.name');
            }
            await host.api.routing.virtualModels.delete(modelName);
            host.feedback.show(i18n.t('modelDetail.notifications.modelDeleted', { model: displayName }), 'info');
            host.pageResources.setTimeout(() => host.router.navigate('models'), 400);
            return;
        }
        setModelDetailDeleteBusy(host, true, i18n.t('modelDetail.delete.deleting'));
        updateModelDetailDeleteProgress(host, {
            show: true,
            progress: 0,
            message: i18n.t('modelDetail.delete.preparing')
        });
        const pluginName = toTrimmedString(host.model?.plugin) || toTrimmedString(host.model?.provider) || toTrimmedString(host.modelId?.split(':')[0]);
        const started = await host.startTaskAction(buildModelApiPath(host.requireModelId()), {
            method: 'DELETE',
            handlers: {
                onProgress: (payload: JsonValue) => {
                    const record = isObject(payload) ? payload : null;
                    const progressCandidate = record ? (record['progress'] ?? record['percentage']) : null;
                    const progress = isNumber(progressCandidate) ? progressCandidate : null;
                    const messageCandidate = record ? record['message'] : null;
                    const message = toTrimmedString(messageCandidate) || i18n.t('modelDetail.delete.deleting');
                    updateModelDetailDeleteProgress(host, { show: true, progress, message, state: 'info' });
                },
                onComplete: (payload: JsonValue) => {
                    const record = isObject(payload) ? payload : null;
                    const messageCandidate = record ? record['message'] : null;
                    const message = toTrimmedString(messageCandidate) || i18n.t('modelDetail.delete.success');
                    updateModelDetailDeleteProgress(host, { show: true, progress: 100, message, state: 'success' });
                },
                onStreamError: (payload: JsonValue) => {
                    const record = isObject(payload) ? payload : null;
                    const progressCandidate = record ? record['progress'] : null;
                    const progress = isNumber(progressCandidate) ? progressCandidate : null;
                    const messageCandidate = record ? (record['message'] ?? record['error']) : null;
                    const message = toTrimmedString(messageCandidate) || i18n.t('modelDetail.delete.failed');
                    updateModelDetailDeleteProgress(host, { show: true, progress, message, state: 'error' });
                },
                onError: (payload: JsonValue) => {
                    const record = isObject(payload) ? payload : null;
                    const messageCandidate = record ? record['message'] : null;
                    const message = toTrimmedString(messageCandidate) || i18n.t('modelDetail.delete.failed');
                    updateModelDetailDeleteProgress(host, { show: true, message, state: 'error' });
                }
            },
            operation: {
                type: 'model-delete',
                plugin: pluginName,
                pluginName: pluginName,
                modelId: host.model?.id || host.requireModelId(),
                displayName: displayName,
                cancelable: false
            }
        });
        if (!isStreamHandle(started)) {
            throw new Error('Model deletion stream did not provide a valid handle');
        }
        host.activeDeletionStream = started;
        let resultRaw: StreamFinishedValue = null;
        try {
            resultRaw = await started.finished;
        } finally {
            if (host.activeDeletionStream === started) {
                host.activeDeletionStream = null;
            }
        }
        const result = isObject(resultRaw) ? resultRaw : null;
        const cancelled = result ? result['cancelled'] : null;
        const detached = result && 'detached' in result ? result['detached'] : null;
        const status = result && 'status' in result ? result['status'] : undefined;
        if (!result || (isBoolean(cancelled) && cancelled) || isCancelledTaskStatus(isString(status) ? status : undefined) || detached === true) {
            clearModelDetailDeleteProgressState(host);
            return;
        }
        const successCandidate = result['success'];
        if (isBoolean(successCandidate) && successCandidate === false) {
            const messageCandidate = result['message'];
            const message = toTrimmedString(messageCandidate) || i18n.t('modelDetail.delete.failed');
            throw createTaskFailureError(result, message);
        }
        const messageCandidate = result['message'];
        const message = toTrimmedString(messageCandidate) || null;
        if (message) {
            host.feedback.show(message, 'info');
        }
    });
};

export { deleteModelDetailModel, stopModelDetailPlugin };
