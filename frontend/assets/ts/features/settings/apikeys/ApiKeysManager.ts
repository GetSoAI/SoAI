/* SoAI - Settings feature API keys manager [frontend/assets/ts/features/settings/apikeys/ApiKeysManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindDataActionListener, createDataActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { applyProgressWidths } from '@core/ui/progressWidths.ts';
import { SettingsSectionLifecycle } from '@features/settings/sectionLifecycle.ts';
import { createSettingsCapabilityAvailability, markSettingsCapabilityFailed, markSettingsCapabilityReady, settleSettingsCapability, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';
import { API_KEYS_ACTION_CREATE, API_KEYS_ACTION_DELETE, API_KEYS_ACTION_DELETE_ALL, API_KEYS_ACTION_MANAGE_QUOTA, API_KEYS_ACTION_REVOKE, API_KEYS_ACTION_ROTATE, isApiKeysActionId, type ApiKeysActionId } from '@features/settings/apikeys/constants.ts';
import { createApiKeyFlow, runApiKeyAction } from '@features/settings/apikeys/controller.ts';
import { optionalApiKeyButton, requireActionKeyId, requireButton, requireCheckbox, requireElement, requireHTMLElement } from '@features/settings/apikeys/dom.ts';
import { hasRevokedApiKeys } from '@features/settings/apikeys/filters.ts';
import { startApiKeyQuotaLiveUpdates } from '@features/settings/apikeys/quotaLiveUpdates.ts';
import { showApiKeyQuotaModal } from '@features/settings/apikeys/quotaModal.ts';
import type { ApiKeyOperation, ApiKeysManagerDependencies, ApiKeysManagerHost } from '@features/settings/apikeys/types.ts';
import { renderApiKeysSection } from '@features/settings/apikeys/view.ts';

class ApiKeysManager {
    readonly #host: ApiKeysManagerHost;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();
    #quotaLiveTimer: number | null = null;
    #quotaLiveRequestInFlight: boolean = false;
    #quotaLiveGeneration: number = 0;
    #reloadInProgress: boolean = false;
    #reloadSequence: number = 0;
    #createFlowInFlight: boolean = false;
    #availability: SettingsCapabilityAvailability = createSettingsCapabilityAvailability();

    constructor({ host }: ApiKeysManagerDependencies) {
        if (!host) {
            throw new Error('ApiKeysManager requires a host');
        }
        this.#host = host;
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(renderApiKeysSection(this.#host, this.#availability));
    }

    #rerender(): void {
        renderSettingsSection({
            container: requireElement(this.#host.view, 'api-keys-content'),
            render: () => this.render(),
            renderMarkup: (container, markup): void => this.#host.view.pageDom.updateHtml(container, markup),
            afterRender: (container): void => applyProgressWidths(container, (element: Element, property: string, value: string | null): void => this.#host.view.pageDom.updateStyle(element, property, value)),
            bind: (): void => this.setupEventListeners(),
            filter: (): void => this.#host.search.filterSettings(),
            hasSearchQuery: (): boolean => this.#host.search.hasSearchQuery()
        });
    }

    setupEventListeners(): void {
        this.dispose();
        if (!this.#host.api.isAdmin()) {
            return;
        }
        this.#lifecycle.mount();

        const root = requireHTMLElement(this.#host.view, 'api-keys-content');
        const createButton = requireButton(this.#host.view, 'api-keys-create-btn', root);
        if (requireTrimmedDataAttribute(createButton, 'action', 'API keys create button') !== API_KEYS_ACTION_CREATE) {
            throw new Error('API keys create button must declare settings.apiKeys.create action');
        }

        const deleteAllButton = optionalApiKeyButton('api-keys-delete-all-btn', root);
        if (deleteAllButton !== null && requireTrimmedDataAttribute(deleteAllButton, 'action', 'API keys delete-all button') !== API_KEYS_ACTION_DELETE_ALL) {
            throw new Error('API keys delete-all button must declare settings.apiKeys.deleteAll action');
        }

        requireHTMLElement(this.#host.view, 'api-keys-list', root);

        if (hasRevokedApiKeys(this.#host.state.getApiKeys())) {
            const showRevokedToggle = requireCheckbox(this.#host.view, 'api-keys-show-revoked', root);
            showRevokedToggle.checked = this.#host.state.getShowRevokedKeys();
            this.#host.view.updatePreferenceToggleLabel(showRevokedToggle, showRevokedToggle.checked);
            this.#lifecycle.addCleanup(
                this.#host.view.pageResources.on(showRevokedToggle, 'change', async (): Promise<void> => {
                    const checked = showRevokedToggle.checked;
                    this.#host.state.setShowRevokedKeys(checked);
                    this.#host.view.updatePreferenceToggleLabel(showRevokedToggle, checked);
                    await this.reload();
                })
            );
        }

        bindDataActionListener({
            root,
            eventType: 'click',
            signal: this.#lifecycle.createAbortSignal('api-keys-actions-dispose'),
            isAction: isApiKeysActionId,
            preventDefault: 'always',
            mouseButton: 'primary',
            ignoreDisabled: true,
            beforeEvent: (eventObject: Event): boolean => eventObject.defaultPrevented,
            onAction: createDataActionDispatcher<ApiKeysActionId>({
                [API_KEYS_ACTION_CREATE]: async (): Promise<void> => await this.showCreateModal(),
                [API_KEYS_ACTION_DELETE_ALL]: async (): Promise<void> => await this.deleteAllKeys(),
                [API_KEYS_ACTION_MANAGE_QUOTA]: async ({ actionElement }): Promise<void> => await this.showQuotaModal(requireActionKeyId(actionElement)),
                [API_KEYS_ACTION_REVOKE]: async ({ actionElement }): Promise<void> => await this.#handleKeyAction('revoke', requireActionKeyId(actionElement)),
                [API_KEYS_ACTION_ROTATE]: async ({ actionElement }): Promise<void> => await this.#handleKeyAction('rotate', requireActionKeyId(actionElement)),
                [API_KEYS_ACTION_DELETE]: async ({ actionElement }): Promise<void> => await this.#handleKeyAction('delete', requireActionKeyId(actionElement))
            })
        });
        this.#startQuotaLiveUpdates(root);
    }

    dispose(): void {
        try {
            this.#lifecycle.dispose('api-keys-dispose');
        } finally {
            this.#quotaLiveGeneration += 1;
            this.#reloadInProgress = false;
            this.#quotaLiveRequestInFlight = false;
            this.#clearQuotaLiveTimer();
        }
    }

    async reload(): Promise<void> {
        const reloadRun = this.#lifecycle.beginReload('api-keys-reload');
        if (reloadRun === null) {
            return;
        }

        this.#quotaLiveGeneration += 1;
        this.#reloadSequence += 1;
        const reloadSequence = this.#reloadSequence;
        this.#reloadInProgress = true;
        try {
            const [keysResult, quotaResult] = await Promise.all([settleSettingsCapability(() => this.#host.api.listApiKeys(true)), settleSettingsCapability(() => this.#host.api.listApiKeyQuotaStatus())]);
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return;
            }
            let successfulCapabilities = 0;
            if (keysResult.succeeded && keysResult.value) {
                this.#host.state.setApiKeys(keysResult.value);
                successfulCapabilities += 1;
            } else {
                this.#reportReloadFailure(keysResult.error, 'keys');
            }
            if (quotaResult.succeeded && quotaResult.value) {
                this.#host.state.setApiKeyQuotaSummaries(quotaResult.value);
                successfulCapabilities += 1;
            } else {
                this.#reportReloadFailure(quotaResult.error, 'quota');
            }
            this.#availability = successfulCapabilities === 2 ? markSettingsCapabilityReady() : markSettingsCapabilityFailed(this.#availability, successfulCapabilities > 0);
            this.#rerender();
            if (successfulCapabilities < 2) {
                this.#host.notifications.feedback.show(i18n.t('settings.apiKeys.errors.reloadFailed'), 'error');
            }
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return;
            }
            this.#host.notifications.feedback.handle(ensureError(error), 'API keys reload');
            this.#host.notifications.feedback.show(i18n.t('settings.apiKeys.errors.reloadFailed'), 'error');
        } finally {
            if (this.#reloadSequence === reloadSequence) {
                this.#reloadInProgress = false;
            }
        }
    }

    #reportReloadFailure(error: Error | null, capability: 'keys' | 'quota'): void {
        const runtimeError = error ?? new Error(`API ${capability} reload failed`);
        this.#host.notifications.feedback.handle(runtimeError, `API ${capability} reload`);
    }

    async showQuotaModal(keyId: string): Promise<void> {
        const apiKey = this.#host.state.getApiKeys().find((candidate) => candidate.keyId === keyId) ?? null;
        if (!apiKey) {
            throw new Error('API key not found in current state');
        }
        let shouldReload = false;
        await this.#host.execution.runWithBoundary('settings:showApiKeyQuotaModal', async () => {
            const quotaResponse = await this.#host.api.getApiKeyQuota(keyId);
            const updated = await showApiKeyQuotaModal(this.#host, apiKey, quotaResponse);
            if (!updated) {
                return;
            }
            shouldReload = true;
        });
        if (shouldReload && this.#lifecycle.isMounted) {
            await this.reload();
        }
    }

    #clearQuotaLiveTimer(): void {
        if (this.#quotaLiveTimer === null) {
            return;
        }
        this.#host.view.clearTimer(this.#quotaLiveTimer);
        this.#quotaLiveTimer = null;
    }

    #startQuotaLiveUpdates(root: HTMLElement): void {
        this.#clearQuotaLiveTimer();
        this.#quotaLiveRequestInFlight = false;
        const cleanup = startApiKeyQuotaLiveUpdates({
            host: this.#host,
            root,
            getIsMounted: (): boolean => this.#lifecycle.isMounted,
            getIsReloading: (): boolean => this.#reloadInProgress,
            getUpdateGeneration: (): number => this.#quotaLiveGeneration,
            getRequestInFlight: (): boolean => this.#quotaLiveRequestInFlight,
            setRequestInFlight: (value: boolean): void => {
                this.#quotaLiveRequestInFlight = value;
            },
            setTimerId: (timerId: number | null): void => {
                this.#quotaLiveTimer = timerId;
            },
            clearTimer: (): void => this.#clearQuotaLiveTimer()
        });
        this.#lifecycle.addCleanup(() => {
            cleanup();
            this.#quotaLiveRequestInFlight = false;
            this.#clearQuotaLiveTimer();
        });
    }

    async showCreateModal(): Promise<void> {
        if (this.#createFlowInFlight) {
            return;
        }
        this.#createFlowInFlight = true;
        try {
            await createApiKeyFlow(this.#host, () => this.reload());
        } finally {
            this.#createFlowInFlight = false;
        }
    }

    async deleteAllKeys(): Promise<void> {
        await this.#host.execution.confirmAndExecute(
            'settings:deleteAllApiKeys',
            {
                title: i18n.t('settings.apiKeys.confirmDeleteAll.title'),
                message: i18n.t('settings.apiKeys.confirmDeleteAll.message'),
                confirmText: i18n.t('settings.apiKeys.actions.delete'),
                cancelText: i18n.t('common.cancel'),
                variant: 'danger'
            },
            () => this.#host.api.deleteAllApiKeys(),
            i18n.t('settings.apiKeys.notifications.deleteAllSuccess'),
            () => this.reload(),
            null
        );
    }

    async #handleKeyAction(action: ApiKeyOperation, keyId: string): Promise<void> {
        await runApiKeyAction(this.#host, action, keyId, () => this.reload());
    }
}

export { ApiKeysManager };
