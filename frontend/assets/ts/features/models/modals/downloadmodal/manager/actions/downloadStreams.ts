/* SoAI - Models feature download streams [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/downloadStreams.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scrollDownloadModalSectionIntoView } from '@features/models/modals/downloadmodal/manager/scrolling.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { buildDownloadRequest } from '@features/models/modals/downloadmodal/manager/actions/downloadRequest.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { runModelDownload } from '@features/models/downloads/modelDownloadRun.ts';
import { updateDownloadBadge } from '@features/models/modals/downloadmodal/manager/view.ts';
import { MODEL_DOWNLOAD_OPERATION_TYPE } from '@features/models/modelDownloadOperation.ts';

const downloadModel = async (runtime: DownloadModalManagerRuntime): Promise<void> => {
    const request = buildDownloadRequest(runtime);
    if (!request) {
        return;
    }
    const outcome = await runModelDownload({
        request,
        startDownload: (downloadRequest, options) => runtime.host.execution.modelActions.startDownload(downloadRequest, options),
        handlers: runtime.host.execution.createStreamHandlers(MODEL_DOWNLOAD_OPERATION_TYPE, i18n.t('models.loading.downloading'), {
            onProgress: (_candidate: JsonValue | null | undefined) => undefined
        }),
        tracker: runtime.host.execution.streams,
        failMessage: i18n.t('models.notifications.downloadFailed'),
        onAdmitted: () => scrollDownloadModalSectionIntoView(runtime, 'operation-progress-list'),
        onStarted: () => {
            runtime.state.acceptedCatalogMutation = true;
            updateDownloadBadge(runtime);
        }
    });
    if (outcome.status === 'rejected') {
        runtime.host.session.showNotification(outcome.reason === 'max_concurrent' ? i18n.t('models.notifications.maxConcurrentDownloads') : i18n.t('models.notifications.alreadyDownloading'), 'warning');
        return;
    }
    updateDownloadBadge(runtime);
    if (outcome.status === 'failed') {
        showOperationFailureNotification({
            error: outcome.error,
            fallbackMessage: i18n.t('models.notifications.downloadFailed'),
            rawMessage: true,
            showNotification: (message, level): void => runtime.host.session.showNotification(message, level)
        });
        return;
    }
    if (outcome.status !== 'finished') {
        return;
    }
    if (outcome.message) {
        runtime.host.session.showNotification(outcome.message, outcome.isCompleteEvent ? 'download' : 'info');
    } else if (outcome.isCompleteEvent) {
        runtime.host.session.showNotification(i18n.t('models.notifications.downloadSuccess'), 'download');
    }
    if (outcome.isCompleteEvent) {
        const streamManager = runtime.host.execution.requireStreamManager();
        await Promise.allSettled([streamManager.refresh(MODELS, { allowDiscovery: true }), streamManager.refresh(PLUGINS, { allowDiscovery: true })]);
    }
};

export { downloadModel };
