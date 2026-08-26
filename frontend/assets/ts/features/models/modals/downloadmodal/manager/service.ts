/* SoAI - Models feature manager service [frontend/assets/ts/features/models/modals/downloadmodal/manager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { buildManualResourceMessage } from '@core/discovery/manualResourceMessage.ts';
import { requireInputElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { toTrustedHtml } from '@core/security/public.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { getManualDiscoveryState } from '@features/models/modals/downloadmodal/manager/state.ts';

const ensureManualDiscoveryDetails = async (runtime: DownloadModalManagerRuntime, forceRefresh = false): Promise<ReturnType<typeof getManualDiscoveryState> | null> => {
    if (!runtime.host.session.isAdmin()) {
        return null;
    }
    const state = getManualDiscoveryState(runtime);
    if (state.loaded && !forceRefresh) {
        return state;
    }
    if (state.promise) {
        return state.promise;
    }

    state.loading = true;
    state.error = null;
    state.promise = (async (): Promise<ReturnType<typeof getManualDiscoveryState> | null> => {
        try {
            const payload = await runtime.host.session.api.models.manualInstall();
            if (!runtime.host.session.isAdmin()) {
                state.loaded = false;
                state.modelsPath = '';
                state.resolvedPath = '';
                return null;
            }
            state.modelsPath = payload.configuredPath;
            state.resolvedPath = payload.resolvedPath;
            state.loaded = true;
            state.error = null;
            return state;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DownloadModalController', 'Failed to load manual discovery configuration', runtimeError);
            state.loaded = false;
            state.error = runtimeError;
            throw runtimeError;
        } finally {
            state.loading = false;
            state.promise = null;
        }
    })();

    return state.promise;
};

const updateManualPathField = (runtime: DownloadModalManagerRuntime, details: ReturnType<typeof getManualDiscoveryState> | null): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const input = requireInputElement(resolver, modalUiSelector(modalId, 'manual-models-path'), 'Download modal manual-models-path', modalRoot);
    const value = toTrimmedString(details?.resolvedPath);
    runtime.host.view.updateProperty(input, 'value', value);
    setTooltipText(input, value || i18n.t('models.modal.manualAdd.pathPlaceholder'));
    updateManualCopyControl(runtime, value);
};

const updateManualCopyControl = (runtime: DownloadModalManagerRuntime, pathValue: string): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const button = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-copy-path'), modalRoot);
    const supported = runtime.host.session.getClipboardService().isSupported();
    const hasPath = Boolean(pathValue);

    if (!(button instanceof HTMLButtonElement)) {
        throw new TypeError('Download modal manual copy button must be a button');
    }
    setControlDisabledState(button, !(supported && hasPath));
    if (!supported) {
        setTooltipText(button, i18n.t('common.clipboard.copyUnavailable'));
        return;
    }
    if (!hasPath) {
        setTooltipText(button, i18n.t('models.modal.manualAdd.copyUnavailable'));
        return;
    }
    setTooltipText(button, '');
};

const updateManualDiscoveryMessage = async (runtime: DownloadModalManagerRuntime): Promise<void> => {
    if (!runtime.host.session.isAdmin()) {
        return;
    }
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const message = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-discovery-text'), modalRoot);
    const state = getManualDiscoveryState(runtime);
    const token = Symbol('manualDiscovery');
    state.token = token;

    runtime.host.view.updateText(message, i18n.t('models.modal.manualAdd.loading'));
    updateManualCopyControl(runtime, '');
    updateManualPathField(runtime, null);

    try {
        const details = await ensureManualDiscoveryDetails(runtime);
        if (state.token !== token || !runtime.host.session.isAdmin()) {
            return;
        }
        if (!details) {
            runtime.host.view.updateText(message, i18n.t('models.modal.manualAdd.error'));
            return;
        }

        const manualMessage = buildManualResourceMessage({
            sanitizeHtml: runtime.host.session.sanitizer.html,
            folderPath: details.modelsPath,
            defaultFolderName: i18n.t('models.modal.manualAdd.defaultModelsFolderName'),
            resolvedPath: details.resolvedPath,
            renderDescription: (modelsFolder) => i18n.t('models.modal.manualAdd.description', { modelsFolder }),
            renderDescriptionWithResolvedPath: ({ folder, resolvedPath }) =>
                i18n.t('models.modal.manualAdd.descriptionWithResolvedPath', {
                    modelsFolder: folder,
                    resolvedPath
                })
        });
        runtime.host.view.updateHTML(message, toTrustedHtml(manualMessage));
        updateManualPathField(runtime, details);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Failed to update manual discovery message', runtimeError);
        if (state.token !== token || !runtime.host.session.isAdmin()) {
            return;
        }
        runtime.host.view.updateText(message, i18n.t('models.modal.manualAdd.error'));
    } finally {
        if (state.token === token) {
            state.token = null;
        }
    }
};

const handleManualDiscovery = async (runtime: DownloadModalManagerRuntime, _event?: Event): Promise<void> => {
    if (!runtime.host.session.isAdmin()) {
        return;
    }
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const button = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-discovery-button'), modalRoot);
    if (!(button instanceof HTMLButtonElement)) {
        throw new TypeError('Download modal manual discovery button must be a button');
    }
    setControlDisabledState(button, true);
    runtime.host.view.toggleClassName(button, CSS_CLASSES.LOADING, true);

    try {
        await runtime.host.session.api.models.discover();
        runtime.state.acceptedCatalogMutation = true;
        runtime.host.session.showNotification(i18n.t('models.notifications.manualDiscoveryStarted'), 'info');
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Failed to trigger manual discovery', runtimeError);
        runtime.host.session.showNotification(
            i18n.t('models.notifications.manualDiscoveryFailed', {
                error: i18n.t('common.errors.unknown')
            }),
            'error'
        );
    } finally {
        runtime.host.view.toggleClassName(button, CSS_CLASSES.LOADING, false);
        if (!runtime.host.session.isAdmin()) {
            return;
        }
        setControlDisabledState(button, false);
    }
};

const handleManualPathCopy = async (runtime: DownloadModalManagerRuntime, _event?: Event): Promise<void> => {
    if (!runtime.host.session.isAdmin()) {
        return;
    }
    if (!runtime.host.session.getClipboardService().isSupported()) {
        runtime.host.session.showNotification(i18n.t('common.clipboard.copyUnavailable'), 'warning');
        return;
    }

    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const value = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'manual-models-path'), 'Download modal manual-models-path', modalRoot).value);
    if (!value) {
        runtime.host.session.showNotification(i18n.t('models.modal.manualAdd.copyUnavailable'), 'warning');
        return;
    }

    const successMessage = i18n.t('models.modal.manualAdd.copySuccess');
    await runtime.host.session.copyToClipboard(value, {
        notify: (message: string, type: NotificationType) => {
            if (type === 'copy') {
                runtime.host.session.showNotification(successMessage, 'copy');
                return;
            }
            runtime.host.session.showNotification(message, type);
        }
    });
};

const handleManualOpenFileExplorer = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    if (!runtime.host.session.isAdmin()) {
        return;
    }
    runtime.host.session.modals.close(runtime.modalId);
    runtime.host.session.setLocationHash('#fileExplorer');
};

export { ensureManualDiscoveryDetails, handleManualDiscovery, handleManualOpenFileExplorer, handleManualPathCopy, updateManualCopyControl, updateManualDiscoveryMessage, updateManualPathField };
