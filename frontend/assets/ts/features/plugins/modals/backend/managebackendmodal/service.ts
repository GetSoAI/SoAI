/* SoAI - Plugins feature manage backend modal service [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { canCheckPluginBackend, canUpdatePluginBackend } from '@core/plugins/backendUpdates.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { BackendUpdateComparison } from '@features/plugins/modals/backend/managebackendmodal/backendUpdateComparison.ts';
import { MANAGE_BACKEND_MODAL_ID } from '@features/plugins/modals/backendModals.ts';
import { startManageBackendInstall, startManageBackendUninstall, startManageBackendUpdate, type ManageBackendOperationDependencies } from '@features/plugins/modals/backend/managebackendmodal/backendOperations.ts';
import { attachManageBackendOperationPanel, detachManageBackendOperationPanel } from '@features/plugins/modals/backend/managebackendmodal/operations.ts';
import { clearManageState, createManageInitialState } from '@features/plugins/modals/backend/managebackendmodal/state.ts';
import type { BackendManagerDependencies, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import { confirmManageBackendUninstall } from '@features/plugins/modals/backend/managebackendmodal/uninstallConfirmation.ts';
import { loadManageBackendVariants } from '@features/plugins/modals/backend/managebackendmodal/variants.ts';
import { clearManageBackendModalView, renderManageBackendInfo, renderManageBackendWarning, resetManageBackendButtons, setManageBackendButtonsDisabled, syncManageBackendFooterActions } from '@features/plugins/modals/backend/managebackendmodal/view.ts';

class ManageBackendModalManager {
    readonly modalId = MANAGE_BACKEND_MODAL_ID;
    readonly #host: BackendManagerDependencies['host'];
    #variantAbort: AbortController | null = null;
    readonly #variantLoadToken = new SequenceToken();
    readonly #operationToken = new SequenceToken();
    protected state: ManageState;
    #dependencies: BackendManagerDependencies;
    #operationPanel: TaskOperationPanel | null = null;
    #pendingCatalogRefresh = false;
    readonly #comparison: BackendUpdateComparison;

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
        this.#comparison = new BackendUpdateComparison(dependencies, this.state, this.modalId, this.#reconcileCatalogVariants);
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

        this.#comparison.dispose();
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

        this.#variantLoadToken.invalidate();
        this.#variantAbort?.abort();
        this.#operationToken.invalidate();
        this.#pendingCatalogRefresh = false;
        this.state.currentPlugin = plugin;
        this.state.updateInfo = null;
        this.state.backendVariantsReady = false;
        this.state.backendVariantsLoading = false;
        this.state.backendVariantSaving = false;
        this.state.operationActive = false;
        this.#host.status.setCurrentManagingPlugin(plugin);
        this.#host.status.setCurrentUpdateInfo(null);

        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.#host.view.setDataAttribute(modalRoot, 'pluginName', plugin.name);
        const title = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'title'), modalRoot);
        this.#host.view.updateText(title, mode === 'install' ? i18n.t('plugins.modal.installBackend.titleFormat', { plugin: this.#host.operations.formatPluginName(String(plugin.name)) }) : i18n.t('plugins.modal.manageBackend.title'));

        resetManageBackendButtons({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot);
        const hasBackendAction = syncManageBackendFooterActions({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, plugin);
        renderManageBackendInfo(this.#dependencies, this.modalId, modalRoot, plugin, hasBackendAction);
        renderManageBackendWarning(this.#dependencies, this.modalId, modalRoot, plugin);
        setManageBackendButtonsDisabled({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, true);
        if (hasBackendAction) {
            this.#loadVariants(modalRoot, plugin);
        }
        this.#operationPanel = attachManageBackendOperationPanel(this.#operationPanel, this.modalId, String(plugin.name));
        this.#host.view.modals.open(this.modalId);
        this.#host.status.subscribeModalLedUpdates();
        this.#comparison.bind();
    }

    #loadVariants(modalRoot: HTMLElement, plugin: PluginRecord): void {
        const variantToken = this.#variantLoadToken.next();
        this.#variantAbort?.abort();
        const abort = new AbortController();
        this.#variantAbort = abort;
        terminateHandledPromise(loadManageBackendVariants({ ...this.#dependencies, state: this.state, signal: abort.signal, variantLoadToken: this.#variantLoadToken, invalidateComparison: () => this.#comparison.invalidate(), flushCatalogRefresh: this.#flushCatalogRefresh }, this.modalId, modalRoot, plugin, variantToken));
    }

    handleRetryBackendVariants(): void {
        const plugin = this.state.currentPlugin;
        if (!plugin || this.state.operationActive || this.state.backendVariantsLoading || this.state.backendVariantSaving || !this.#host.catalog.isFresh()) return;
        this.#refreshAfterOperation(plugin);
    }

    async handleCheckBackendUpdate(): Promise<void> {
        if (this.state.operationActive || this.#comparison.checking) return;
        if (!this.state.currentPlugin?.name) {
            return;
        }
        if (!this.state.backendVariantsReady) {
            this.#host.operations.showNotification(i18n.t('plugins.modal.backendVariants.loadFailed'), 'error');
            return;
        }

        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const checkButton = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'check-update'), modalRoot);
        const mode = this.#host.view.dom.getData(checkButton, 'mode');
        const current = this.#host.catalog.getPlugin(this.state.currentPlugin.name);
        if (!current || !this.#host.catalog.isFresh()) return;
        const access = this.#host.policy.backendUpdateAccess(current);
        if (!(mode === 'update' ? canUpdatePluginBackend(current, access) : canCheckPluginBackend(access))) return;
        this.state.currentPlugin = current;
        if (mode === 'update') {
            const plugin = this.state.currentPlugin;
            if (plugin) {
                await startManageBackendUpdate(this.#operationDependencies(), plugin);
            }
            return;
        }
        if (mode === 'check') {
            await this.#comparison.check();
            return;
        }
        throw new Error('Backend update button requires a valid mode');
    }

    handleStartBackendInstall(): void {
        if (this.state.operationActive || this.#comparison.checking) return;
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
        if (this.state.operationActive || this.#comparison.checking) return;
        const plugin = this.state.currentPlugin;
        if (!plugin?.name) {
            return;
        }
        if (!this.state.backendVariantsReady) {
            this.#host.operations.showNotification(i18n.t('plugins.modal.backendVariants.loadFailed'), 'error');
            return;
        }

        const modalSessionToken = this.#operationToken.value;
        const confirmed = await confirmManageBackendUninstall(this.#host.operations, plugin);
        if (!confirmed) {
            return;
        }
        if (!this.#operationToken.isActive(modalSessionToken) || this.state.currentPlugin?.name !== plugin.name || !this.state.backendVariantsReady || this.state.operationActive || this.#comparison.checking) {
            return;
        }

        await startManageBackendUninstall(this.#operationDependencies(), plugin);
    }

    #operationDependencies(): ManageBackendOperationDependencies {
        return { ...this.#dependencies, modalId: this.modalId, operationToken: this.#operationToken, state: this.state, refreshAfterOperation: this.#refreshAfterOperation, flushCatalogRefresh: this.#flushCatalogRefresh };
    }

    #reconcileCatalogVariants = (backendChanged: boolean): void => {
        if (backendChanged) this.#pendingCatalogRefresh = true;
        this.#flushCatalogRefresh();
    };

    #flushCatalogRefresh = (): void => {
        const plugin = this.state.currentPlugin;
        if (!this.#pendingCatalogRefresh || !plugin?.name || this.state.operationActive || this.state.backendVariantsLoading || this.state.backendVariantSaving || !this.#host.catalog.isFresh() || !this.#host.catalog.getPlugin(plugin.name)) return;
        this.#refreshAfterOperation(plugin);
    };

    #refreshAfterOperation = (plugin: PluginRecord): void => {
        if (!plugin.name || this.state.currentPlugin?.name !== plugin.name) {
            return;
        }
        this.#pendingCatalogRefresh = false;
        const currentPlugin = this.#host.catalog.getPlugin(plugin.name);
        if (currentPlugin) {
            plugin = currentPlugin;
            this.state.currentPlugin = currentPlugin;
        }
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.state.updateInfo = null;
        this.state.backendVariantsReady = false;
        this.#host.status.setCurrentUpdateInfo(null);
        resetManageBackendButtons({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot);
        const hasBackendAction = syncManageBackendFooterActions({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, plugin);
        renderManageBackendInfo(this.#dependencies, this.modalId, modalRoot, plugin, hasBackendAction);
        renderManageBackendWarning(this.#dependencies, this.modalId, modalRoot, plugin);
        setManageBackendButtonsDisabled({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, modalRoot, true);
        if (hasBackendAction) {
            this.#loadVariants(modalRoot, plugin);
        }
    };

    #clearModalState(): void {
        this.#pendingCatalogRefresh = false;
        clearManageBackendModalView({ host: this.#host, classNames: this.#dependencies.classNames }, this.modalId, this.#host.view.modals.requireElement(this.modalId));
        clearManageState(this.state);
        this.#host.status.setCurrentManagingPlugin(null);
        this.#host.status.setCurrentUpdateInfo(null);
    }

    onModalClosed(): void {
        this.#comparison.dispose();
        this.#variantLoadToken.invalidate();
        this.#variantAbort?.abort();
        this.#variantAbort = null;
        this.#operationToken.invalidate();
        this.#host.status.unsubscribeModalLedUpdates();
        this.#operationPanel = detachManageBackendOperationPanel(this.#operationPanel);
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#comparison.dispose();
        this.#variantLoadToken.invalidate();
        this.#variantAbort?.abort();
        this.#variantAbort = null;
        this.#operationToken.invalidate();
        this.#operationPanel = detachManageBackendOperationPanel(this.#operationPanel);
        this.#clearModalState();
        this.#host.status.unsubscribeModalLedUpdates();
    }
}

export { ManageBackendModalManager };
