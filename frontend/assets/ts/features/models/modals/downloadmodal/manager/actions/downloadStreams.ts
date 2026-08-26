/* SoAI - Models feature download streams [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/downloadStreams.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { buildDownloadRequest } from '@features/models/modals/downloadmodal/manager/actions/downloadRequest.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { buildRequestSignature, countActiveModelDownloads, getActiveModelDownloadOperations, operationMatchesRequest } from '@features/models/modals/downloadmodal/manager/modelDownloadOperations.ts';
import { updateDownloadBadge } from '@features/models/modals/downloadmodal/manager/view.ts';

const scrollOperationProgressToTop = (runtime: DownloadModalManagerRuntime): void => {
    const modalRoot = runtime.host.session.modals.requireElement(runtime.modalId);
    runtime.host.session.requireHTMLElement('.download-model-modal-scroll', modalRoot).scrollTop = 0;
};

const downloadModel = async (runtime: DownloadModalManagerRuntime): Promise<void> => {
    const request = buildDownloadRequest(runtime);
    if (!request) {
        return;
    }
    const activeDownloads = getActiveModelDownloadOperations();
    if (countActiveModelDownloads(runtime) >= 5) {
        runtime.host.session.showNotification(i18n.t('models.notifications.maxConcurrentDownloads'), 'warning');
        return;
    }
    const signature = buildRequestSignature(request);
    if ((signature && runtime.state['activeDownloadSignatures'].has(signature)) || activeDownloads.some((operation) => operationMatchesRequest(operation, request))) {
        runtime.host.session.showNotification(i18n.t('models.notifications.alreadyDownloading'), 'warning');
        return;
    }
    if (signature) {
        runtime.state['activeDownloadSignatures'].add(signature);
    }
    const key = 'model-download';
    const message = i18n.t('models.loading.downloading');
    try {
        scrollOperationProgressToTop(runtime);
        const stream = await runtime.host.execution.modelActions.startDownload(request, {
            handlers: runtime.host.execution.createStreamHandlers(key, message, {
                onProgress: (_candidate: JsonValue | null | undefined) => undefined
            })
        });
        runtime.state.acceptedCatalogMutation = true;
        updateDownloadBadge(runtime);
        const settled = await settleTrackedTaskStream({
            tracker: runtime.host.execution.streams,
            stream,
            keyPrefix: key,
            failMessage: i18n.t('models.notifications.downloadFailed')
        });
        const eventMessage = settled.message;
        if (settled.cancelled || settled.detached) {
            return;
        }
        if (eventMessage) {
            runtime.host.session.showNotification(eventMessage, settled.isCompleteEvent ? 'download' : 'info');
        } else if (settled.isCompleteEvent) {
            runtime.host.session.showNotification(i18n.t('models.notifications.downloadSuccess'), 'download');
        }

        if (settled.isCompleteEvent) {
            const streamManager = runtime.host.execution.requireStreamManager();
            await Promise.allSettled([streamManager.refresh(MODELS, { allowDiscovery: true }), streamManager.refresh(PLUGINS, { allowDiscovery: true })]);
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Failed to download model', runtimeError);
        showOperationFailureNotification({
            error: runtimeError,
            fallbackMessage: i18n.t('models.notifications.downloadFailed'),
            rawMessage: true,
            showNotification: (message, level): void => runtime.host.session.showNotification(message, level)
        });
    } finally {
        if (signature) {
            runtime.state['activeDownloadSignatures'].delete(signature);
        }
        updateDownloadBadge(runtime);
    }
};

export { downloadModel };
