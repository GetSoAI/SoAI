/* SoAI - Manage backend comparison ownership and catalog reconciliation [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/backendUpdateComparison.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { canCheckPluginBackend, hasPluginBackendUpdate } from '@core/plugins/backendUpdates.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import type { BackendManagerDependencies, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import { renderManageBackendInfoStatus } from '@features/plugins/modals/backend/managebackendmodal/backendInfo.ts';
import { resetManageBackendButtons, setManageBackendButtonsDisabled, showManageBackendNoUpdateAvailable, showManageBackendUpdateAvailable, syncManageBackendFooterActions } from '@features/plugins/modals/backend/managebackendmodal/view.ts';

class BackendUpdateComparison {
    readonly #dependencies: BackendManagerDependencies;
    readonly #state: ManageState;
    readonly #modalId: string;
    readonly #token = new SequenceToken();
    #abort: AbortController | null = null;
    #unsubscribe: (() => void) | null = null;
    #fingerprint = '';
    #backendFingerprint = '';
    readonly #onCatalogReconciled: (backendChanged: boolean) => void;
    #unsubscribeAccess: (() => void) | null = null;

    constructor(dependencies: BackendManagerDependencies, state: ManageState, modalId: string, onCatalogReconciled: (backendChanged: boolean) => void) {
        this.#dependencies = dependencies;
        this.#state = state;
        this.#modalId = modalId;
        this.#onCatalogReconciled = onCatalogReconciled;
    }

    get checking(): boolean {
        return this.#abort !== null;
    }

    invalidate(): void {
        this.#token.invalidate();
        if (this.#abort) {
            this.#abort.abort();
            const button = this.#dependencies.host.view.optionalHTMLElement(modalUiSelector(this.#modalId, 'check-update'));
            if (button instanceof HTMLButtonElement) clearLoadingButtonIfNeeded(button);
        }
        this.#abort = null;
    }

    dispose(): void {
        this.invalidate();
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#unsubscribeAccess?.();
        this.#unsubscribeAccess = null;
        this.#fingerprint = '';
        this.#backendFingerprint = '';
    }

    bind(): void {
        this.dispose();
        this.#reconcile();
        this.#unsubscribe = this.#dependencies.host.catalog.subscribe(this.#reconcile, { emitInitial: false });
        this.#unsubscribeAccess = this.#dependencies.host.policy.subscribeBackendUpdateAccess(this.#reconcile);
    }

    #reconcile = (): void => {
        const { host } = this.#dependencies;
        const managingPlugin = this.#state.currentPlugin;
        if (!managingPlugin?.name) return;
        const name = managingPlugin.name;
        const plugin = host.catalog.getPlugin(name);
        const fresh = host.catalog.isFresh();
        const backendStatus = plugin ? host.status.getBackendStatus(plugin) : null;
        const fingerprint = stableJsonStringify({ fresh, backendStatus, access: plugin ? host.policy.backendUpdateAccess(plugin) : null, advisory: plugin?.backendUpdate ?? null, state: plugin?.state ?? null, backendVersion: plugin?.backendVersion ?? null, packageVersion: plugin?.versionSoaiplugin ?? null });
        const modalRoot = host.view.modals.requireElement(this.#modalId);
        renderManageBackendInfoStatus(host.view, host.status, plugin ?? managingPlugin, modalRoot, host.status.getStatusManager(), undefined, fresh && plugin !== null);
        if (fingerprint === this.#fingerprint) return;
        this.#fingerprint = fingerprint;
        this.invalidate();
        this.#state.updateInfo = null;
        host.status.setCurrentUpdateInfo(null);
        if (plugin) {
            this.#state.currentPlugin = plugin;
            host.status.setCurrentManagingPlugin(plugin);
        }
        const backendFingerprint = fresh ? stableJsonStringify({ present: plugin !== null, status: backendStatus, version: plugin?.backendVersion ?? null, packageVersion: plugin?.versionSoaiplugin ?? null }) : null;
        const backendChanged = plugin !== null && backendFingerprint !== null && this.#backendFingerprint !== '' && backendFingerprint !== this.#backendFingerprint;
        if (backendFingerprint !== null) this.#backendFingerprint = backendFingerprint;
        this.#onCatalogReconciled(backendChanged);
        if (this.#state.operationActive) return;
        resetManageBackendButtons(this.#dependencies, this.#modalId, modalRoot);
        const actionable = syncManageBackendFooterActions(this.#dependencies, this.#modalId, modalRoot, plugin);
        if (fresh && plugin && hasPluginBackendUpdate(plugin) && plugin.backendUpdate) {
            const info: PluginBackendUpdateStatus = { installed: true, updateAvailable: true, currentVersion: plugin.backendUpdate.currentVersion, latestVersion: plugin.backendUpdate.latestVersion, error: null };
            this.#state.updateInfo = info;
            host.status.setCurrentUpdateInfo(info);
            showManageBackendUpdateAvailable({ ...this.#dependencies, state: this.#state }, this.#modalId, modalRoot, info);
        }
        setManageBackendButtonsDisabled(this.#dependencies, this.#modalId, modalRoot, !fresh || !plugin || !actionable || !this.#state.backendVariantsReady);
    };

    async check(): Promise<void> {
        const currentPlugin = this.#state.currentPlugin;
        if (!currentPlugin?.name || !this.#dependencies.host.catalog.isFresh() || !canCheckPluginBackend(this.#dependencies.host.policy.backendUpdateAccess(currentPlugin))) {
            return;
        }

        this.invalidate();
        const abortController = new AbortController();
        this.#abort = abortController;
        const token = this.#token.next();

        const modalRoot = this.#dependencies.host.view.modals.requireElement(this.#modalId);
        const checkButtonCandidate = this.#dependencies.host.view.requireHTMLElement(modalUiSelector(this.#modalId, 'check-update'), modalRoot);
        if (!(checkButtonCandidate instanceof HTMLButtonElement)) {
            throw new TypeError('Manage backend update check requires an HTMLButtonElement');
        }
        const checkButton = checkButtonCandidate;
        setManageBackendButtonsDisabled({ host: this.#dependencies.host, classNames: this.#dependencies.classNames }, this.#modalId, modalRoot, true);
        beginLoadingButton(checkButton);

        let response: PluginBackendUpdateStatus;
        try {
            response = await this.#dependencies.host.operations.checkBackendUpdate(currentPlugin.name, { signal: abortController.signal });
        } catch (error) {
            if (!this.#token.isActive(token) || abortController.signal.aborted) return;
            const runtimeError = ensureError(error);
            errorHandler.error('ManageBackendModalManager', i18n.t('plugins.notifications.updateCheckFailed'), runtimeError);
            this.#dependencies.host.operations.showNotification(i18n.t('plugins.notifications.updateCheckFailed'), 'error');
            return;
        } finally {
            if (this.#token.isActive(token)) {
                this.#abort = null;
                const plugin = this.#dependencies.host.catalog.getPlugin(currentPlugin.name);
                const actionable = syncManageBackendFooterActions(this.#dependencies, this.#modalId, modalRoot, plugin);
                setManageBackendButtonsDisabled(this.#dependencies, this.#modalId, modalRoot, !this.#state.backendVariantsReady || !this.#dependencies.host.catalog.isFresh() || !actionable);
                clearLoadingButtonIfNeeded(checkButton);
            }
        }

        if (!this.#token.isActive(token)) {
            return;
        }
        if (this.#state.currentPlugin?.name !== currentPlugin.name || !this.#dependencies.host.catalog.isFresh() || !canCheckPluginBackend(this.#dependencies.host.policy.backendUpdateAccess(currentPlugin))) {
            return;
        }

        const info = response;
        if (info.error || info.installed === false) {
            this.#dependencies.host.operations.showNotification(i18n.t('plugins.notifications.updateCheckFailed'), 'error');
            return;
        }
        this.#state.updateInfo = info;
        this.#dependencies.host.status.setCurrentUpdateInfo(info);

        if (info?.updateAvailable) {
            showManageBackendUpdateAvailable(
                {
                    host: this.#dependencies.host,
                    classNames: this.#dependencies.classNames,
                    state: this.#state,
                    security: this.#dependencies.security
                },
                this.#modalId,
                modalRoot,
                info
            );
            return;
        }

        this.#dependencies.host.operations.showNotification(i18n.t('plugins.notifications.noUpdates'), 'info');
        showManageBackendNoUpdateAvailable(
            {
                host: this.#dependencies.host,
                classNames: this.#dependencies.classNames,
                state: this.#state,
                security: this.#dependencies.security
            },
            this.#modalId,
            modalRoot
        );
    }
}

export { BackendUpdateComparison };
