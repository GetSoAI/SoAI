/* SoAI - Plugin download manager operations [frontend/assets/ts/features/plugins/modals/downloadmanager/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { pluginDownloadPath, pluginUploadPath } from '@core/api/endpoints/uiPaths.ts';
import { buildManualResourceMessage } from '@core/discovery/manualResourceMessage.ts';
import { taskProgressPayloadToOperationProgress } from '@core/operationprogress/taskProgressAdapter.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { toTrustedHtml } from '@core/security/public.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasFunctionProperties, isPlainObject } from '@core/typeGuards.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { DownloadManagerHost, ManualPluginState, OperationMeta, ProgressReporter } from '@features/plugins/modals/downloadmanager/contracts.ts';

const isProgressReporter = <T>(value: T | JsonValue | null | undefined): value is T & ProgressReporter => {
    if (!isPlainObject(value)) {
        return false;
    }
    return hasFunctionProperties(value, ['update', 'remove', 'clear', 'destroy', 'hasActiveOperations']);
};

interface DownloadManagerProgressScope {
    modalId: string;
    host: DownloadManagerHost;
    getProgressReporter: () => ProgressReporter;
    setBusy: (isBusy: boolean) => void;
}

interface InstallFromUrlOptions extends DownloadManagerProgressScope {
    url: string;
}

interface InstallFromManualFileOptions {
    host: DownloadManagerHost;
    modalId: string;
    file: File | null;
    getProgressReporter: () => ProgressReporter;
    setBusy: (isBusy: boolean) => void;
}

interface ManualPluginRequestOptions {
    host: DownloadManagerHost;
    manualState: ManualPluginState;
    forceRefresh: boolean;
}

interface ManualPluginMessageOptions {
    host: DownloadManagerHost;
    descriptionElement: Element;
    sequence: number;
    isCurrentSequence: (sequence: number) => boolean;
    setCopyControlState: (pathValue: string) => void;
    setManualPluginPath: (details: ManualPluginState | null) => void;
    ensureManualPluginDetails: () => Promise<ManualPluginState | null>;
}

const installFromUrl = async ({ host, modalId, getProgressReporter, setBusy, url }: InstallFromUrlOptions): Promise<void> => {
    if (!url) {
        host.session.showNotification(i18n.t('plugins.notifications.enterUrl'), 'error');
        return;
    }

    setBusy(true);
    const downloadKey = 'plugin-download';
    const loadingMessage = i18n.t('plugins.loading.installing');
    getProgressReporter().update(downloadKey, { progress: 0, message: loadingMessage, state: 'info' });

    const handlers = host.execution.createStreamHandlers(downloadKey, loadingMessage, {
        onProgress: (data: JsonValue | null | undefined): void => getProgressReporter().update(downloadKey, taskProgressPayloadToOperationProgress(data))
    });

    const operationMeta: OperationMeta = {
        type: 'plugin-download',
        pluginName: url,
        url,
        source: 'url'
    };

    let hasError = false;
    let cancelled = false;
    let detached = false;
    let completionMessage = '';
    let isCompleteEvent = false;

    try {
        const stream = await host.execution.startTaskAction(pluginDownloadPath(), {
            method: 'POST',
            body: { url },
            handlers,
            operation: operationMeta
        });
        const settled = await settleTrackedTaskStream({
            tracker: host.execution.streams,
            stream,
            keyPrefix: downloadKey,
            failMessage: i18n.t('plugins.notifications.installFailed')
        });
        cancelled = settled.cancelled;
        detached = settled.detached;
        completionMessage = settled.message;
        isCompleteEvent = settled.isCompleteEvent;
    } catch (error) {
        hasError = true;
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadManager', i18n.t('plugins.notifications.installFailed'), runtimeError);
        showOperationFailureNotification({
            error: runtimeError,
            notificationMessage: i18n.t('plugins.notifications.installFailed'),
            showNotification: (message, level): void => host.session.showNotification(message, level)
        });
    } finally {
        getProgressReporter().remove(downloadKey);
        setBusy(false);
    }

    if (hasError || cancelled || detached) {
        return;
    }
    host.session.showNotification(completionMessage ? completionMessage : i18n.t('plugins.notifications.installSuccess'), isCompleteEvent ? 'download' : 'info');
    if (isCompleteEvent) {
        host.view.modals.close(modalId);
    }
};

const installFromFile = async ({ host, modalId, file, getProgressReporter, setBusy }: InstallFromManualFileOptions): Promise<void> => {
    if (!file) {
        host.session.showNotification(i18n.t('plugins.notifications.selectFile'), 'error');
        return;
    }

    setBusy(true);
    const uploadKey = generateSecureId({ prefix: 'plugin-upload', separator: '-' });
    const uploadMessage = i18n.t('taskManager.badges.pluginUpload');
    getProgressReporter().update(uploadKey, {
        progress: 0,
        message: uploadMessage,
        state: 'downloading'
    });
    let result: ApiResponsePayload | null = null;
    try {
        result = await host.execution.api.uploadFile(
            pluginUploadPath(),
            file,
            {},
            {
                onUploadProgress: (progress): void => {
                    getProgressReporter().update(uploadKey, {
                        progress: progress.percent ?? 0,
                        message: uploadMessage,
                        state: 'downloading'
                    });
                }
            }
        );
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadManager', i18n.t('plugins.notifications.uploadFailed'), runtimeError);
        showOperationFailureNotification({
            error: runtimeError,
            notificationMessage: i18n.t('plugins.notifications.uploadFailed'),
            showNotification: (message, level): void => host.session.showNotification(message, level)
        });
    } finally {
        getProgressReporter().remove(uploadKey);
        setBusy(false);
    }
    if (result) {
        host.session.showNotification(i18n.t('plugins.notifications.uploadAccepted'), 'info');
        host.view.modals.close(modalId);
    }
};

const ensureManualPluginDetails = async ({ host, manualState, forceRefresh = false }: ManualPluginRequestOptions): Promise<ManualPluginState | null> => {
    if (!host.session.isAdmin()) {
        return null;
    }
    if (manualState.loaded && !forceRefresh) {
        return manualState;
    }
    if (manualState.promise) {
        return manualState.promise;
    }

    manualState.loading = true;
    manualState.error = null;

    manualState.promise = (async (): Promise<ManualPluginState | null> => {
        try {
            const payload = await host.execution.api.plugins.manualInstall();
            if (!host.session.isAdmin()) {
                manualState.loaded = false;
                manualState.pluginsPath = '';
                manualState.resolvedPath = '';
                return null;
            }
            manualState.pluginsPath = payload.configuredPath;
            manualState.resolvedPath = payload.resolvedPath;
            manualState.loaded = true;
            manualState.error = null;
            return manualState;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DownloadManager', 'Failed to load manual plugin configuration', runtimeError);
            manualState.loaded = false;
            manualState.error = runtimeError;
            throw runtimeError;
        } finally {
            manualState.loading = false;
            manualState.promise = null;
        }
    })();

    return manualState.promise;
};

const updateManualPluginMessage = async ({ host, descriptionElement, sequence, isCurrentSequence, setCopyControlState, setManualPluginPath, ensureManualPluginDetails }: ManualPluginMessageOptions): Promise<void> => {
    host.view.updateText(descriptionElement, i18n.t('plugins.modal.addPlugin.manualLoading'));
    setCopyControlState('');
    setManualPluginPath(null);

    try {
        const details = await ensureManualPluginDetails();
        if (!isCurrentSequence(sequence)) {
            return;
        }
        if (details) {
            const message = buildManualResourceMessage({
                sanitizeHtml: host.session.sanitizeHtml,
                folderPath: details.pluginsPath,
                defaultFolderName: i18n.t('plugins.labels.defaultFolderName'),
                resolvedPath: details.resolvedPath,
                renderDescription: (pluginsFolder) => i18n.t('plugins.modal.addPlugin.manualDescription', { pluginsFolder }),
                renderDescriptionWithResolvedPath: ({ folder, resolvedPath }) =>
                    i18n.t('plugins.modal.addPlugin.manualDescriptionWithResolvedPath', {
                        pluginsFolder: folder,
                        resolvedPath
                    })
            });
            host.view.updateHTML(descriptionElement, toTrustedHtml(message));
            setManualPluginPath(details);
            return;
        }
        host.view.updateText(descriptionElement, i18n.t('plugins.modal.addPlugin.manualError'));
    } catch (error) {
        if (!isCurrentSequence(sequence)) {
            return;
        }
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadManager', 'Failed to update manual plugin message', runtimeError);
        host.view.updateText(descriptionElement, i18n.t('plugins.modal.addPlugin.manualError'));
    }
};

export { ensureManualPluginDetails, installFromFile, installFromUrl, isProgressReporter, updateManualPluginMessage };
