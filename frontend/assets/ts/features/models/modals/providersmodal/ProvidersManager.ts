/* SoAI - Providers modal refresh and mutation ownership [frontend/assets/ts/features/models/modals/providersmodal/ProvidersManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_MANAGE_PROVIDERS } from '@core/models/pageActions.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { isInstanceOf } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { MODELS_PROVIDERS_MODAL_ID } from '@features/models/modals/constants.ts';
import type { LoadProvidersOptions, ProvidersManagerDependencies } from '@features/models/modals/providersmodal/contracts.ts';
import { normalizeProviderRecord } from '@features/models/modals/providersmodal/providerRecords.ts';
import { renderProvidersListMarkup } from '@features/models/modals/providersmodal/providersListRendering.ts';
import { ProvidersRefreshController } from '@features/models/modals/providersmodal/ProvidersRefreshController.ts';
import type { ProviderRefreshFailure, ProvidersRefreshResult } from '@features/models/modals/providersmodal/providersRefreshContracts.ts';

class ProvidersManager {
    readonly modalId = MODELS_PROVIDERS_MODAL_ID;
    readonly #dependencies: ProvidersManagerDependencies;
    readonly #refreshController: ProvidersRefreshController;
    readonly #deleteFlows = new Map<string, Promise<void>>();
    #providerEventUnsubscribe: (() => void) | null = null;
    #isModalOpen = false;
    #modalGeneration = 0;
    #highlightTimerId: number | null = null;
    #focusPlugin = '';
    #closeAfterAuthoritativeEmpty = false;

    constructor(dependencies: ProvidersManagerDependencies) {
        if (!dependencies) throw new Error('ProvidersManager requires dependencies');
        this.#dependencies = dependencies;
        this.#refreshController = new ProvidersRefreshController({
            fetchPlugin: (pluginName, signal) => this.#dependencies.requestProviders(pluginName, signal),
            publish: (result) => this.#publishRefresh(result),
            reportFailure: (failures) => this.#reportRefreshFailure(failures),
            concurrency: 4
        });
    }

    async openProvidersModal(_event?: Event): Promise<void> {
        const context = this.#dependencies.consumeInitialActionContext();
        this.#focusPlugin = toTrimmedString(context?.plugin);
        this.#ensureProviderUpdates();
        this.#isModalOpen = true;
        this.#modalGeneration += 1;
        this.#closeAfterAuthoritativeEmpty = false;
        this.#dependencies.modals.open(this.modalId);
        this.#refreshController.open(this.#activePluginNames());
        this.#renderLoading();
        await this.#refreshController.refresh('initial');
    }

    closeProvidersModal(_event?: Event): void {
        this.#dependencies.modals.close(this.modalId);
    }

    async loadProvidersList(options: LoadProvidersOptions = {}): Promise<void> {
        if (!this.#isModalOpen) return;
        const focusPlugin = toTrimmedString(options.focusPlugin);
        if (focusPlugin) this.#focusPlugin = focusPlugin;
        this.#refreshController.updatePlugins(this.#activePluginNames());
        this.#refreshController.markDirty('manual');
        await this.#refreshController.refresh('manual');
    }

    async handleProviderDelete(event: Event, button: Element): Promise<void> {
        event.stopPropagation();
        const providerId = this.#dependencies.getData(button, 'providerId');
        const pluginName = this.#dependencies.getData(button, 'plugin_name');
        const providerName = this.#dependencies.getData(button, 'provider_name');
        const revisionRaw = this.#dependencies.getData(button, 'providerRevision');
        const revision = revisionRaw === null ? Number.NaN : Number(revisionRaw);
        if (!providerId || !pluginName || !Number.isSafeInteger(revision) || revision < 0) {
            throw new Error('Provider delete button requires providerId, plugin_name, and revision');
        }
        const operationKey = `${pluginName.trim()}:${providerId.trim()}`;
        const existing = this.#deleteFlows.get(operationKey);
        if (existing) return existing;
        const task = this.#runProviderDelete(pluginName, providerId, providerName ?? '', revision).finally((): void => {
            if (this.#deleteFlows.get(operationKey) === task) this.#deleteFlows.delete(operationKey);
        });
        this.#deleteFlows.set(operationKey, task);
        return task;
    }

    updateProviderButtonVisibility(): void {
        const manageButton = this.#dependencies.optionalUI(MODELS_ACTION_MANAGE_PROVIDERS);
        if (manageButton?.classList.contains('u-hidden') === true) this.#dependencies.removeClassName(manageButton, 'u-hidden');
    }

    onModalClosed(): void {
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#clearModalState();
    }

    async #runProviderDelete(pluginName: string, providerId: string, providerName: string, revision: number): Promise<void> {
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('models.confirmations.deleteProvider'),
            message: i18n.t('models.confirmations.deleteProviderMessage', { provider: providerName }),
            confirmText: i18n.t('models.confirmations.deleteProviderConfirm'),
            cancelText: i18n.t('models.confirmations.deleteProviderCancel')
        });
        if (!confirmed) return;
        try {
            await this.#dependencies.deleteProvider(pluginName, providerId, revision);
        } catch (error) {
            errorHandler.error('ProvidersController', 'Failed to delete provider', ensureError(error));
            this.#dependencies.showNotification(i18n.t('models.notifications.providerDeleteFailed'), 'error');
            return;
        }
        this.#dependencies.showNotification(i18n.t('models.notifications.providerDeleteSuccess', { provider: providerName }), 'success');
        if (this.#isModalOpen) this.#refreshController.markDirty('provider-delete');
        try {
            await this.#dependencies.loadPlugins({ force: true });
        } catch (error) {
            errorHandler.warn('ProvidersController', 'Provider delete committed but plugin refresh failed', ensureError(error));
        }
        if (!this.#isModalOpen) return;
        this.#refreshController.updatePlugins(this.#activePluginNames());
        this.#closeAfterAuthoritativeEmpty = true;
        await this.#refreshController.refresh('provider-delete');
        this.updateProviderButtonVisibility();
    }

    #publishRefresh(result: ProvidersRefreshResult): void {
        if (!this.#isModalOpen) return;
        const providersList = this.#requireProvidersList();
        if (result.status === 'unavailable') {
            this.#dependencies.updateHTML(providersList, uiHtml`<div class="ui-empty-state--simple">${i18n.t('models.modal.providers.loadFailed')}</div>`);
            return;
        }
        const providers = result.providers.map((provider) => normalizeProviderRecord(provider));
        if (providers.length === 0) {
            if (result.status === 'degraded') {
                this.#dependencies.updateHTML(providersList, uiHtml`<div class="form-disclaimer form-disclaimer-warning providers-degraded-state" role="status">${i18n.t('models.modal.providers.degraded')}</div>`);
                return;
            }
            this.#dependencies.updateHTML(providersList, uiHtml`<div class="ui-empty-state--simple">${i18n.t('models.modal.providers.noProviders')}</div>`);
            if (this.#closeAfterAuthoritativeEmpty && result.status === 'ready') this.#dependencies.modals.close(this.modalId);
            return;
        }
        const providersMarkup = renderProvidersListMarkup(providers, this.#dependencies.sanitizer);
        const degraded = result.status === 'degraded' ? uiHtml`<div class="form-disclaimer form-disclaimer-warning providers-degraded-state" role="status">${i18n.t('models.modal.providers.degraded')}</div>` : uiHtml``;
        this.#dependencies.updateHTML(providersList, uiHtml`${degraded}${providersMarkup}`);
        this.#applyFocus(providersList);
    }

    #reportRefreshFailure(failures: readonly ProviderRefreshFailure[]): void {
        const first = failures[0];
        if (!first) return;
        errorHandler.warn('ProvidersController', `${String(failures.length)} provider refresh request(s) failed`, first.error);
    }

    #applyFocus(providersList: Element): void {
        const focusPlugin = this.#focusPlugin;
        if (!focusPlugin) return;
        const generation = this.#modalGeneration;
        this.#dependencies.requestAnimationFrame((): void => {
            if (!this.#isModalOpen || generation !== this.#modalGeneration || this.#focusPlugin !== focusPlugin) return;
            for (const item of this.#dependencies.queryUI('.provider-item', providersList)) {
                if (!isInstanceOf(item, HTMLElement)) throw new Error('ProvidersManager requires provider item elements to be HTMLElements');
                if (toTrimmedString(item.dataset['pluginName']) !== focusPlugin) continue;
                this.#focusPlugin = '';
                this.#clearHighlightState();
                scrollElementIntoView(item, { behavior: 'smooth', block: 'center' });
                item.classList.add('provider-item-highlight');
                this.#highlightTimerId = this.#dependencies.setTimer((): void => {
                    item.classList.remove('provider-item-highlight');
                    this.#highlightTimerId = null;
                }, 3000);
                return;
            }
        });
    }

    #renderLoading(): void {
        this.#dependencies.updateHTML(this.#requireProvidersList(), uiHtml`<div class="loading-container"><div class="loading-spinner"></div><span>${i18n.t('models.loading.providers')}</span></div>`);
    }

    #requireProvidersList(): Element {
        const root = this.#dependencies.modals.requireElement(this.modalId);
        const list = this.#dependencies.optionalUI(modalUiSelector(this.modalId, 'providers-list'), root);
        if (!list) throw new Error('ProvidersManager requires providers-list element');
        return list;
    }

    #activePluginNames(): readonly string[] {
        return this.#dependencies.getActiveProviderPlugins().map((plugin) => {
            const name = toTrimmedString(plugin.name);
            if (!name) throw new Error('Provider plugin name must be a non-empty string');
            return name;
        });
    }

    #ensureProviderUpdates(): void {
        if (this.#providerEventUnsubscribe) return;
        this.#providerEventUnsubscribe = this.#dependencies.subscribeProviderUpdate((): void => {
            if (!this.#isModalOpen) return;
            this.#refreshController.markDirty('provider-event');
            void this.#refreshController.refresh('provider-event').catch((error) => errorHandler.warn('ProvidersController', 'Provider event refresh failed', ensureError(error)));
        });
    }

    #clearHighlightState(): void {
        this.#dependencies.clearTimer(this.#highlightTimerId);
        this.#highlightTimerId = null;
        const root = this.#dependencies.modals.requireElement(this.modalId);
        for (const item of this.#dependencies.queryUI('.provider-item-highlight', root)) {
            if (item instanceof HTMLElement) item.classList.remove('provider-item-highlight');
        }
    }

    #clearModalState(): void {
        if (!this.#isModalOpen && !this.#providerEventUnsubscribe) return;
        this.#isModalOpen = false;
        this.#modalGeneration += 1;
        this.#focusPlugin = '';
        this.#refreshController.close();
        this.#clearHighlightState();
        const list = this.#dependencies.optionalUI(modalUiSelector(this.modalId, 'providers-list'), this.#dependencies.modals.requireElement(this.modalId));
        if (list) this.#dependencies.updateHTML(list, '');
        this.#providerEventUnsubscribe?.();
        this.#providerEventUnsubscribe = null;
    }
}

export { ProvidersManager };
