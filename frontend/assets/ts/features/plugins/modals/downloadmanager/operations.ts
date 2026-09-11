/* SoAI - Plugin download manager operations [frontend/assets/ts/features/plugins/modals/downloadmanager/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { pluginDownloadPath, pluginUploadPath } from '@core/api/endpoints/uiPaths.ts';
import { isNetworkError } from '@core/apiError.ts';
import { buildManualResourceMessage } from '@core/discovery/manualResourceMessage.ts';
import { taskProgressPayloadToOperationProgress } from '@core/operationprogress/taskProgressAdapter.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { createMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { toTrustedHtml } from '@core/security/public.ts';
import { parseAcceptedTaskId } from '@core/tasks/operationPayloads.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
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

interface InstallTaskLifecycleOptions extends DownloadManagerProgressScope {
    operationKey: string;
    failureMessage: string;
    acquireStream: () => Promise<StreamActionHandle>;
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

const executeInstallTaskLifecycle = async ({ host, modalId, getProgressReporter, setBusy, operationKey, failureMessage, acquireStream }: InstallTaskLifecycleOptions): Promise<void> => {
    let cancelled = false;
    let detached = false;
    let completionMessage = '';
    let isCompleteEvent = false;

    try {
        const stream = await acquireStream();
        const settled = await settleTrackedTaskStream({
            tracker: host.execution.streams,
            stream,
            keyPrefix: operationKey,
            trackingKey: operationKey,
            failMessage: failureMessage
        });
        cancelled = settled.cancelled;
        detached = settled.detached;
        completionMessage = settled.message;
        isCompleteEvent = settled.isCompleteEvent;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError)) {
            return;
        }
        errorHandler.error('DownloadManager', failureMessage, runtimeError);
        showOperationFailureNotification({
            error: runtimeError,
            notificationMessage: failureMessage,
            showNotification: (message, level): void => host.session.showNotification(message, level)
        });
        return;
    } finally {
        host.execution.streams.release(operationKey, { cancel: false });
        getProgressReporter().remove(operationKey);
        setBusy(false);
    }

    if (cancelled || detached) {
        return;
    }
    host.session.showNotification(completionMessage ? completionMessage : i18n.t('plugins.notifications.installSuccess'), isCompleteEvent ? 'download' : 'info');
    if (isCompleteEvent) {
        host.view.modals.close(modalId);
    }
};

const installFromUrl = async ({ host, modalId, getProgressReporter, setBusy, url }: InstallFromUrlOptions): Promise<void> => {
    if (!url) {
        host.session.showNotification(i18n.t('plugins.notifications.enterUrl'), 'error');
        return;
    }

    setBusy(true);
    const downloadKey = generateSecureId({ prefix: 'plugin-download', separator: '-' });
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

    await executeInstallTaskLifecycle({
        host,
        modalId,
        getProgressReporter,
        setBusy,
        operationKey: downloadKey,
        failureMessage: i18n.t('plugins.notifications.installFailed'),
        acquireStream: () =>
            host.execution.startTaskAction(pluginDownloadPath(), {
                method: 'POST',
                body: { url },
                handlers,
                operation: operationMeta
            })
    });
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

    const handlers = host.execution.createStreamHandlers(uploadKey, uploadMessage, {
        onProgress: (data: JsonValue | null | undefined): void => getProgressReporter().update(uploadKey, taskProgressPayloadToOperationProgress(data))
    });
    const taskId = createMutationRequestId();
    const operationMeta: OperationMeta = {
        type: 'plugin-upload',
        pluginName: file.name,
        url: '',
        source: 'file',
        operationKey: uploadKey,
        requestId: taskId
    };
    const uploadController = new AbortController();
    let uploadBodyTransferred = false;
    let cancellationRequested = false;
    host.execution.streams.track(uploadKey, {
        abort: (): void => {
            cancellationRequested = true;
            if (!uploadBodyTransferred) {
                uploadController.abort();
            }
        }
    });

    const trackUploadTask = (): StreamActionHandle => {
        const stream = host.execution.trackAcceptedTask(taskId, {
            handlers,
            operation: operationMeta
        });
        if (cancellationRequested) {
            stream.abort();
        }
        return stream;
    };

    await executeInstallTaskLifecycle({
        host,
        modalId,
        getProgressReporter,
        setBusy,
        operationKey: uploadKey,
        failureMessage: i18n.t('plugins.notifications.uploadFailed'),
        acquireStream: async (): Promise<StreamActionHandle> => {
            try {
                const result = await host.execution.api.uploadFile(
                    pluginUploadPath(),
                    file,
                    {},
                    {
                        signal: uploadController.signal,
                        query: { 'task_id': taskId },
                        onUploadProgress: (progress): void => {
                            if (progress.percent === 100) {
                                uploadBodyTransferred = true;
                            }
                            getProgressReporter().update(uploadKey, {
                                progress: progress.percent ?? 0,
                                message: uploadMessage,
                                state: 'downloading'
                            });
                        }
                    }
                );
                const acceptedTaskId = parseAcceptedTaskId(result, 'Plugin upload response');
                if (acceptedTaskId !== taskId) {
                    throw new Error('Plugin upload response task identity mismatch');
                }
                return trackUploadTask();
            } catch (error) {
                const runtimeError = ensureError(error);
                if (!uploadBodyTransferred || !isNetworkError(runtimeError)) {
                    throw runtimeError;
                }
                return trackUploadTask();
            }
        }
    });
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
