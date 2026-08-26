/* SoAI - Plugins feature download manager service [frontend/assets/ts/features/plugins/modals/downloadmanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { DOWNLOAD_PLUGIN_MODAL_ID } from '@features/plugins/modals/downloadPluginModal.ts';
import type { DownloadManagerHost, DownloadManagerOptions, ManualPluginState, ProgressReporter } from '@features/plugins/modals/downloadmanager/contracts.ts';
import { applyDownloadModalMode, resetDownloadModalUi, resolveConfirmButtonEnabled, setDownloadModalBusyIfPresent, syncDownloadManualInstallVisibility, syncDownloadModalDisclaimerVisibility, syncSelectedPluginFileName, updateManualPluginCopyControl, updateManualPluginPathField } from '@features/plugins/modals/downloadmanager/dom.ts';
import { ensureManualPluginDetails, installFromFile, installFromUrl, isProgressReporter, updateManualPluginMessage } from '@features/plugins/modals/downloadmanager/operations.ts';
import { createManualPluginState } from '@features/plugins/modals/downloadmanager/state.ts';

class PluginDownloadModalManager {
    readonly #host: DownloadManagerHost;
    readonly #classNames: DownloadManagerOptions['classNames'];
    readonly #modalId = DOWNLOAD_PLUGIN_MODAL_ID;
    #progressReporter: ProgressReporter | null = null;
    readonly #manualPluginToken = new SequenceToken();
    #manualPluginState: ManualPluginState = createManualPluginState();

    constructor({ host, classNames }: DownloadManagerOptions) {
        if (!host) {
            throw new Error('PluginDownloadModalManager requires a host');
        }
        this.#host = host;
        this.#classNames = classNames;
    }

    #getProgressReporter(): ProgressReporter {
        if (this.#progressReporter) {
            return this.#progressReporter;
        }
        const reporterRaw = this.#host.execution.createOperationProgressReporter(modalUiId(this.#modalId, 'operation-progress-list'), {
            onCancel: (key: string): void => this.#host.execution.cancelDownload(key)
        });
        if (!isProgressReporter(reporterRaw)) {
            throw new TypeError('Plugins operation progress reporter must implement ProgressReporter');
        }
        this.#progressReporter = reporterRaw;
        return reporterRaw;
    }

    #hasActiveDownloads(): boolean {
        return this.#progressReporter?.hasActiveOperations() === true;
    }

    #setBusy(isBusy: boolean): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        setDownloadModalBusyIfPresent(this.#host, this.#modalId, isBusy, modalRoot);
    }

    #syncConfirmButtonState(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
        const button = requireButtonElement(resolver, modalUiSelector(this.#modalId, 'confirm-download'), 'Plugin download modal confirm button', modalRoot);
        const enabled = resolveConfirmButtonEnabled(this.#host, this.#modalId, this.#classNames, modalRoot);
        this.#host.view.updateProperty(button, 'disabled', !enabled);
    }

    openDownloadPluginModal(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        resetDownloadModalUi(this.#host, this.#modalId, modalRoot, {
            preserveActiveDownloads: this.#hasActiveDownloads()
        });
        if (!this.#host.session.isAdmin()) {
            this.#manualPluginState = createManualPluginState();
        }
        syncDownloadManualInstallVisibility(this.#host, this.#modalId, this.#classNames, this.#host.session.isAdmin(), modalRoot);
        applyDownloadModalMode(this.#host, this.#modalId, this.#classNames, 'url', modalRoot);
        this.#setBusy(false);
        this.#syncConfirmButtonState();
        this.#host.view.modals.open(this.#modalId);
    }

    handleUrlTabClick(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        applyDownloadModalMode(this.#host, this.#modalId, this.#classNames, 'url', modalRoot);
        this.#syncConfirmButtonState();
    }

    handleFileTabClick(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        applyDownloadModalMode(this.#host, this.#modalId, this.#classNames, 'file', modalRoot);
        this.#syncConfirmButtonState();
    }

    handleManualPluginTabClick(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        if (!this.#host.session.isAdmin()) {
            this.#manualPluginState = createManualPluginState();
            syncDownloadManualInstallVisibility(this.#host, this.#modalId, this.#classNames, false, modalRoot);
            applyDownloadModalMode(this.#host, this.#modalId, this.#classNames, 'url', modalRoot);
            this.#syncConfirmButtonState();
            return;
        }
        applyDownloadModalMode(this.#host, this.#modalId, this.#classNames, 'manual', modalRoot);
        terminateHandledPromise(this.#refreshManualPluginMessage(false));
    }

    handleChooseFileClick(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
        const input = requireInputElement(resolver, modalUiSelector(this.#modalId, 'plugin-file'), 'Plugin download modal file input', modalRoot);
        input.click();
    }

    handlePluginUrlInput(_event: Event): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        syncDownloadModalDisclaimerVisibility(this.#host, this.#modalId, modalRoot);
        this.#syncConfirmButtonState();
    }

    handlePluginFileChange(_event: Event): void {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
        const fileInput = requireInputElement(resolver, modalUiSelector(this.#modalId, 'plugin-file'), 'Plugin download modal file input', modalRoot);
        const name = fileInput.files?.item(0)?.name ?? '';
        syncSelectedPluginFileName(this.#host, this.#modalId, modalRoot, name);
        syncDownloadModalDisclaimerVisibility(this.#host, this.#modalId, modalRoot);
        this.#syncConfirmButtonState();
    }

    async handleConfirmPluginDownload(): Promise<void> {
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        const urlTab = this.#host.view.requireHTMLElement(modalUiSelector(this.#modalId, 'url-tab'), modalRoot);
        const fileTab = this.#host.view.requireHTMLElement(modalUiSelector(this.#modalId, 'file-tab'), modalRoot);
        const manualTab = this.#host.view.requireHTMLElement(modalUiSelector(this.#modalId, 'manual-tab'), modalRoot);
        if (manualTab.classList.contains(this.#classNames.active)) {
            return;
        }
        const getProgressReporter = (): ProgressReporter => this.#getProgressReporter();
        if (urlTab.classList.contains(this.#classNames.active)) {
            const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
            const url = toTrimmedString(requireInputElement(resolver, modalUiSelector(this.#modalId, 'plugin-url'), 'Plugin download modal URL input', modalRoot).value);
            await installFromUrl({
                host: this.#host,
                modalId: this.#modalId,
                url,
                getProgressReporter,
                setBusy: (isBusy: boolean) => this.#setBusy(isBusy)
            });
            return;
        }
        if (fileTab.classList.contains(this.#classNames.active)) {
            const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
            const fileInput = requireInputElement(resolver, modalUiSelector(this.#modalId, 'plugin-file'), 'Plugin download modal file input', modalRoot);
            const file = fileInput.files?.item(0) ?? null;
            await installFromFile({
                host: this.#host,
                modalId: this.#modalId,
                file,
                getProgressReporter,
                setBusy: (isBusy: boolean) => this.#setBusy(isBusy)
            });
        }
    }

    async handleManualPluginPathCopy(): Promise<void> {
        if (!this.#host.session.isAdmin()) {
            return;
        }
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
        const value = toTrimmedString(requireInputElement(resolver, modalUiSelector(this.#modalId, 'manual-plugins-path'), 'Plugin download modal manual plugins path input', modalRoot).value);
        if (!value) {
            this.#host.session.showNotification(i18n.t('plugins.modal.addPlugin.manualCopyUnavailable'), 'warning');
            return;
        }
        await copyTextWithHostClipboardFeedback(
            {
                copyToClipboard: (text, options) => this.#host.session.copyToClipboard(text, options?.notify ? { notify: options.notify } : undefined),
                hasClipboardSupport: () => this.#host.session.hasClipboardSupport(),
                showNotification: (message, type): void => this.#host.session.showNotification(message, type)
            },
            {
                text: value,
                successMessage: i18n.t('plugins.modal.addPlugin.manualCopySuccess'),
                unavailableMessage: i18n.t('common.clipboard.copyUnavailable'),
                unavailableType: 'error'
            }
        );
    }

    handleManualPluginOpenFileExplorer(): void {
        if (!this.#host.session.isAdmin()) {
            return;
        }
        this.#host.view.modals.close(this.#modalId);
        this.#host.session.setLocationHash('#fileExplorer');
    }

    handleManualPluginPowerClick(): void {
        if (!this.#host.session.isAdmin()) {
            return;
        }
        this.#host.view.modals.close(this.#modalId);
        this.#host.session.setLocationHash('#power');
    }

    async #refreshManualPluginMessage(forceRefresh: boolean): Promise<void> {
        if (!this.#host.session.isAdmin()) {
            return;
        }
        const modalRoot = this.#host.view.modals.requireElement(this.#modalId);
        const descriptionElement = this.#host.view.requireHTMLElement(modalUiSelector(this.#modalId, 'manual-description'), modalRoot);
        const sequence = this.#manualPluginToken.next();
        const isCurrentSequence = (candidate: number): boolean => this.#manualPluginToken.isActive(candidate) && this.#host.session.isAdmin();
        const ensureDetails = async (): Promise<ManualPluginState | null> => {
            const details = await ensureManualPluginDetails({
                host: this.#host,
                manualState: this.#manualPluginState,
                forceRefresh
            });
            return details;
        };
        await updateManualPluginMessage({
            host: this.#host,
            descriptionElement,
            sequence,
            isCurrentSequence,
            setCopyControlState: (value: string) => updateManualPluginCopyControl(this.#host, this.#modalId, value, modalRoot),
            setManualPluginPath: (details: ManualPluginState | null) => {
                updateManualPluginPathField(this.#host, this.#modalId, details, modalRoot);
            },
            ensureManualPluginDetails: ensureDetails
        });
    }

    #resetState(clearProgress: boolean): void {
        if (clearProgress) {
            this.#progressReporter?.destroy();
            this.#progressReporter = null;
        }
        this.#manualPluginToken.invalidate();
        this.#manualPluginState = createManualPluginState();
    }

    onModalClosed(): void {
        try {
            this.#setBusy(false);
            this.#resetState(!this.#hasActiveDownloads());
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('PluginDownloadModalManager', 'Dispose failed', runtimeError);
        }
    }

    disposeForPageDestroy(): void {
        try {
            this.#setBusy(false);
            this.#resetState(true);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('PluginDownloadModalManager', 'Dispose failed', runtimeError);
        }
    }
}

export { PluginDownloadModalManager };
export type { DownloadManagerHost };
