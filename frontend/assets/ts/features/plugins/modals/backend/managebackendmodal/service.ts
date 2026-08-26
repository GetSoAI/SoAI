/* SoAI - Plugins feature manage backend modal service [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import type { PluginBackendUpdatesResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import { MANAGE_BACKEND_MODAL_ID } from '@features/plugins/modals/backendModals.ts';
import { startManageBackendInstall, startManageBackendUninstall, startManageBackendUpdate, type ManageBackendOperationDependencies } from '@features/plugins/modals/backend/managebackendmodal/backendOperations.ts';
import { attachManageBackendOperationPanel, detachManageBackendOperationPanel } from '@features/plugins/modals/backend/managebackendmodal/operations.ts';
import { clearManageState, createManageInitialState } from '@features/plugins/modals/backend/managebackendmodal/state.ts';
import type { BackendManagerDependencies, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import { confirmManageBackendUninstall } from '@features/plugins/modals/backend/managebackendmodal/uninstallConfirmation.ts';
import { loadManageBackendVariants } from '@features/plugins/modals/backend/managebackendmodal/variants.ts';
import { clearManageBackendModalView, renderManageBackendInfo, renderManageBackendWarning, resetManageBackendButtons, setManageBackendButtonsDisabled, showManageBackendNoUpdateAvailable, showManageBackendUpdateAvailable, syncManageBackendFooterActions } from '@features/plugins/modals/backend/managebackendmodal/view.ts';

class ManageBackendModalManager {
    readonly modalId = MANAGE_BACKEND_MODAL_ID;
    readonly #host: BackendManagerDependencies['host'];
    readonly #updateCheckToken = new SequenceToken();
    readonly #variantLoadToken = new SequenceToken();
    readonly #operationToken = new SequenceToken();
    protected state: ManageState;
    #dependencies: BackendManagerDependencies;
    #operationPanel: TaskOperationPanel | null = null;

    constructor(dependencies: BackendManagerDependencies) {
        if (!dependencies.host) {
            throw new Error('ManageBackendModalManager requires a host');
        }
        if (!dependencies.classNames?.hidden || !dependencies.classNames?.disabled) {
            throw new Error('ManageBackendModalManager requires classNames.hidden and classNames.disabled');
        }
        if (!dependencies.security) {
            throw new Error('ManageBackendModalManager requires a security module');
        }

        this.#host = dependencies.host;
        this.#dependencies = dependencies;
        this.state = createManageInitialState();
    }

    openInstallBackendModal = (plugin: PluginRecord): void => {
        this.#openBackendModal(plugin, 'install');
    };

    openManageBackendModal = (plugin: PluginRecord): void => {
        this.#openBackendModal(plugin, 'manage');
    };

    #openBackendModal(plugin: PluginRecord, mode: 'install' | 'manage'): void {
        if (!plugin?.name) {
            return;
        }

        this.#updateCheckToken.invalidate();
        if (mode === 'install' && this.#host.policy.isPluginPermanentlyDisabled(plugin)) {
            this.#host.policy.notifyPluginIncompatible(plugin);
            return;
        }
        if (!this.#host.policy.checkBackendInstallationSupport(plugin)) {
            if (mode === 'install') {
                this.#host.operations.showNotification(i18n.t('plugins.notifications.backendNotSupported'), 'warning');
            } else {
                this.#host.operations.showNotification(i18n.t('plugins.notifications.backendManagementNotSupported'), 'warning');
            }
            return;
        }

        this.state.currentPlugin = plugin;
        this.state.updateInfo = null;
        this.state.backendVariantsReady = false;
        this.#host.status.setCurrentManagingPlugin(plugin);
        this.#host.status.setCurrentUpdateInfo(null);
        const variantToken = this.#variantLoadToken.next();

        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const title = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'title'), modalRoot);
        this.#host.view.updateText(title, mode === 'install' ? i18n.t('plugins.modal.installBackend.titleFormat', { plugin: this.#host.operations.formatPluginName(String(plugin.name)) }) : i18n.t('plugins.modal.manageBackend.title'));

        renderManageBackendInfo(this.#dependencies, this.modalId, modalRoot, plugin);
        renderManageBackendWarning(this.#dependencies, this.modalId, modalRoot, plugin);
        resetManageBackendButtons({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot);
        const canManage = syncManageBackendFooterActions({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, plugin);
        setManageBackendButtonsDisabled({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, true);
        if (canManage) {
            terminateHandledPromise(loadManageBackendVariants({ ...this.#dependencies, state: this.state, variantLoadToken: this.#variantLoadToken }, this.modalId, modalRoot, plugin, variantToken));
        }
        this.#operationPanel = attachManageBackendOperationPanel(this.#operationPanel, this.modalId, String(plugin.name));
        this.#host.view.modals.open(this.modalId);
        this.#host.status.subscribeModalLedUpdates();
    }

    async handleCheckBackendUpdate(): Promise<void> {
        if (!this.state.currentPlugin) {
            return;
        }
        if (!this.state.backendVariantsReady) {
            this.#host.operations.showNotification(i18n.t('plugins.modal.backendVariants.loadFailed'), 'error');
            return;
        }

        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const checkButton = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'check-update'), modalRoot);
        const mode = this.#host.view.dom.getData(checkButton, 'mode');
        if (mode === 'update') {
            const plugin = this.state.currentPlugin;
            if (plugin) {
                await startManageBackendUpdate(this.#operationDependencies(), plugin);
            }
            return;
        }
        if (mode === 'check') {
            await this.#checkForBackendUpdate();
            return;
        }
        throw new Error('Backend update button requires a valid mode');
    }

    async #checkForBackendUpdate(): Promise<void> {
        const currentPlugin = this.state.currentPlugin;
        if (!currentPlugin) {
            return;
        }

        const token = this.#updateCheckToken.next();

        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const checkButtonCandidate = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'check-update'), modalRoot);
        if (!(checkButtonCandidate instanceof HTMLButtonElement)) {
            throw new TypeError('Manage backend update check requires an HTMLButtonElement');
        }
        const checkButton = checkButtonCandidate;
        setManageBackendButtonsDisabled({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, true);
        beginLoadingButton(checkButton);

        let response: PluginBackendUpdatesResponse;
        try {
            response = await this.#host.operations.checkUpdates();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ManageBackendModalManager', i18n.t('plugins.notifications.updateCheckFailed'), runtimeError);
            this.#host.operations.showNotification(i18n.t('plugins.notifications.updateCheckFailed'), 'error');
            throw ensureError(error);
        } finally {
            if (this.#updateCheckToken.isActive(token)) {
                setManageBackendButtonsDisabled({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, !this.state.backendVariantsReady);
                clearLoadingButtonIfNeeded(checkButton);
            }
        }

        if (!this.#updateCheckToken.isActive(token)) {
            return;
        }
        if (this.state.currentPlugin?.name !== currentPlugin.name) {
            return;
        }

        const info = response[String(currentPlugin.name)] ?? null;
        this.state.updateInfo = info;
        this.#host.status.setCurrentUpdateInfo(info);

        if (info?.updateAvailable) {
            showManageBackendUpdateAvailable(
                {
                    host: this.#host,
                    classNames: this.#dependencies.classNames,
                    state: this.state,
                    security: this.#dependencies.security
                },
                this.modalId,
                modalRoot,
                info
            );
            return;
        }

        this.#host.operations.showNotification(i18n.t('plugins.notifications.noUpdates'), 'info');
        showManageBackendNoUpdateAvailable(
            {
                host: this.#host,
                classNames: this.#dependencies.classNames,
                state: this.state,
                security: this.#dependencies.security
            },
            this.modalId,
            modalRoot
        );
    }

    handleStartBackendInstall(): void {
        const plugin = this.state.currentPlugin;
        if (!plugin) {
            return;
        }
        if (!this.state.backendVariantsReady) {
            this.#host.operations.showNotification(i18n.t('plugins.modal.backendVariants.loadFailed'), 'error');
            return;
        }
        terminateHandledPromise(startManageBackendInstall(this.#operationDependencies(), plugin));
    }

    async handleUninstallBackend(): Promise<void> {
        const plugin = this.state.currentPlugin;
        if (!plugin?.name) {
            return;
        }

        const confirmed = await confirmManageBackendUninstall(this.#host.operations, plugin);
        if (!confirmed) {
            return;
        }
        if (this.state.currentPlugin?.name !== plugin.name) {
            return;
        }

        await startManageBackendUninstall(this.#operationDependencies(), plugin);
    }

    #operationDependencies(): ManageBackendOperationDependencies {
        return { ...this.#dependencies, modalId: this.modalId, operationToken: this.#operationToken, state: this.state, refreshAfterOperation: this.#refreshAfterOperation };
    }

    #refreshAfterOperation = (plugin: PluginRecord): void => {
        if (this.state.currentPlugin?.name !== plugin.name) {
            return;
        }
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.state.updateInfo = null;
        this.state.backendVariantsReady = false;
        this.#host.status.setCurrentUpdateInfo(null);
        renderManageBackendInfo(this.#dependencies, this.modalId, modalRoot, plugin);
        renderManageBackendWarning(this.#dependencies, this.modalId, modalRoot, plugin);
        resetManageBackendButtons({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot);
        const canManage = syncManageBackendFooterActions({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, plugin);
        setManageBackendButtonsDisabled({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, true);
        if (canManage) {
            const variantToken = this.#variantLoadToken.next();
            terminateHandledPromise(loadManageBackendVariants({ ...this.#dependencies, state: this.state, variantLoadToken: this.#variantLoadToken }, this.modalId, modalRoot, plugin, variantToken));
        }
    };

    #clearModalState(): void {
        clearManageBackendModalView({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, this.#host.view.modals.requireElement(this.modalId));
        clearManageState(this.state);
        this.#host.status.setCurrentManagingPlugin(null);
        this.#host.status.setCurrentUpdateInfo(null);
    }

    onModalClosed(): void {
        this.#updateCheckToken.invalidate();
        this.#variantLoadToken.invalidate();
        this.#host.status.unsubscribeModalLedUpdates();
        this.#operationPanel = detachManageBackendOperationPanel(this.#operationPanel);
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#variantLoadToken.invalidate();
        this.#operationToken.invalidate();
        this.#operationPanel = detachManageBackendOperationPanel(this.#operationPanel);
        this.#clearModalState();
        this.#host.status.unsubscribeModalLedUpdates();
    }
}

export { ManageBackendModalManager };
