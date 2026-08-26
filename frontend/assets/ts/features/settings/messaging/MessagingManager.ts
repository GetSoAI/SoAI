/* SoAI - Owner Messaging accounts manager [frontend/assets/ts/features/settings/messaging/MessagingManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAccount, MessagingAccountUpdate } from '@core/api/contracts/messagingAccountContracts.ts';
import type { ModelCatalogResponse } from '@core/api/contracts/modelCatalogContracts.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindDataActionListener, createDataActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpFormCatalog } from '@core/mcp/configTypes.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { MESSAGING_ACTION_ADD_ACCOUNT, MESSAGING_ACTION_DISABLE_ACCOUNT, MESSAGING_ACTION_EDIT_ACCOUNT, MESSAGING_ACTION_ENABLE_ACCOUNT, MESSAGING_ACTION_REMOVE_ACCOUNT, isMessagingActionId, type MessagingActionId } from '@features/settings/messaging/constants.ts';
import { openMessagingAccountModal } from '@features/settings/messaging/modal.ts';
import { buildMessagingModelOptions } from '@features/settings/messaging/modelOptions.ts';
import { SettingsSectionLifecycle } from '@features/settings/sectionLifecycle.ts';
import type { MessagingManagerDependencies, MessagingManagerHost, MessagingModelCatalogStatus, MessagingModelOption } from '@features/settings/messaging/types.ts';
import { renderMessagingSection } from '@features/settings/messaging/view.ts';

class MessagingManager {
    readonly #host: MessagingManagerHost;
    readonly #lifecycle = new SettingsSectionLifecycle();
    #accounts: MessagingAccount[] = [];
    #models: readonly MessagingModelOption[] = [];
    #modelCatalogStatus: MessagingModelCatalogStatus = 'idle';
    #mcpCatalog: McpFormCatalog | null = null;
    #operationInFlight = false;
    #toolCatalogWarningShown = false;

    constructor({ host }: MessagingManagerDependencies) {
        this.#host = host;
    }

    setModelCatalog(catalog: ModelCatalogResponse): void {
        this.#models = buildMessagingModelOptions(catalog);
        this.#modelCatalogStatus = 'ready';
    }

    setModelCatalogUnavailable(): void {
        this.#models = [];
        this.#modelCatalogStatus = 'error';
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(renderMessagingSection(this.#accounts));
    }

    async reload(): Promise<void> {
        const reloadRun = this.#lifecycle.beginReload('messaging-reload');
        if (reloadRun === null) return;
        const [accounts, mcpCatalog] = await Promise.all([
            this.#host.api.list(),
            this.#host.api.listMcpTools().then(
                (catalog): McpFormCatalog | null => catalog,
                (): null => null
            )
        ]);
        if (!this.#lifecycle.isReloadCurrent(reloadRun)) return;
        this.#accounts = this.#sortAccounts(accounts);
        this.#mcpCatalog = mcpCatalog;
        if (mcpCatalog) {
            this.#toolCatalogWarningShown = false;
        } else if (!this.#toolCatalogWarningShown) {
            this.#toolCatalogWarningShown = true;
            this.#host.feedback.show(i18n.t('settings.messaging.notifications.toolCatalogUnavailable'), 'warning');
        }
        if (this.#lifecycle.isMounted) this.#rerender();
    }

    dispose(): void {
        this.#lifecycle.dispose('messaging-dispose');
        this.#operationInFlight = false;
    }

    setupEventListeners(): void {
        this.#lifecycle.mount();
        const root = narrowHTMLElement(this.#host.pageDom.require('messaging-content'), 'Messaging settings root');
        bindDataActionListener({
            root,
            eventType: 'click',
            signal: this.#lifecycle.createAbortSignal('messaging-actions-dispose'),
            isAction: isMessagingActionId,
            preventDefault: 'always',
            mouseButton: 'primary',
            ignoreDisabled: true,
            onAction: createDataActionDispatcher<MessagingActionId>({
                [MESSAGING_ACTION_ADD_ACCOUNT]: async ({ actionElement }): Promise<void> => await this.#withActionLock(actionElement, () => this.#createAccount()),
                [MESSAGING_ACTION_EDIT_ACCOUNT]: async ({ actionElement }): Promise<void> => await this.#withActionLock(actionElement, () => this.#editAccount(this.#requireAccount(actionElement))),
                [MESSAGING_ACTION_ENABLE_ACCOUNT]: async ({ actionElement }): Promise<void> => await this.#withActionLock(actionElement, () => this.#setEnabled(this.#requireAccount(actionElement), true)),
                [MESSAGING_ACTION_DISABLE_ACCOUNT]: async ({ actionElement }): Promise<void> => await this.#withActionLock(actionElement, () => this.#setEnabled(this.#requireAccount(actionElement), false)),
                [MESSAGING_ACTION_REMOVE_ACCOUNT]: async ({ actionElement }): Promise<void> => await this.#withActionLock(actionElement, () => this.#deleteAccount(this.#requireAccount(actionElement)))
            })
        });
    }

    async #withActionLock(actionElement: HTMLElement, operation: () => Promise<void>): Promise<void> {
        if (this.#operationInFlight) return;
        if (!(actionElement instanceof HTMLButtonElement)) throw new TypeError('Messaging action must be a button');
        this.#operationInFlight = true;
        setControlDisabledState(actionElement, true);
        try {
            await operation();
        } finally {
            this.#operationInFlight = false;
            setControlDisabledState(actionElement, false);
        }
    }

    #requireAccount(element: HTMLElement): MessagingAccount {
        const accountId = requireTrimmedDataAttribute(element, 'accountId', 'Messaging account action');
        const account = this.#accounts.find((candidate) => candidate.accountId === accountId);
        if (!account) throw new Error('Messaging account no longer exists');
        return account;
    }

    #requireEditorCatalogs(): McpFormCatalog | null {
        if (this.#modelCatalogStatus !== 'ready') {
            this.#host.feedback.show(i18n.t('settings.messaging.modelCatalog.unavailable'), 'warning');
            return null;
        }
        if (!this.#mcpCatalog) {
            this.#host.feedback.show(i18n.t('settings.messaging.notifications.toolCatalogUnavailable'), 'warning');
            return null;
        }
        return this.#mcpCatalog;
    }

    #sortAccounts(accounts: readonly MessagingAccount[]): MessagingAccount[] {
        return [...accounts].sort((left, right) => right.updatedAtMs - left.updatedAtMs || left.accountId.localeCompare(right.accountId, 'en'));
    }

    #upsertAccount(account: MessagingAccount): void {
        this.#accounts = this.#sortAccounts([...this.#accounts.filter((candidate) => candidate.accountId !== account.accountId), account]);
        if (this.#lifecycle.isMounted) this.#rerender();
    }

    #removeAccount(accountId: string): void {
        this.#accounts = this.#accounts.filter((candidate) => candidate.accountId !== accountId);
        if (this.#lifecycle.isMounted) this.#rerender();
    }

    #showSaveOutcome(account: MessagingAccount): void {
        if (account.lifecycleState === 'degraded') {
            this.#host.feedback.show(i18n.t('settings.messaging.notifications.accountSavedDegraded'), 'error');
            return;
        }
        this.#host.feedback.show(i18n.t('settings.messaging.notifications.accountSaved'), 'success');
    }

    async #createAccount(): Promise<void> {
        const mcpCatalog = this.#requireEditorCatalogs();
        if (!mcpCatalog) return;
        if (this.#models.length === 0) {
            this.#host.feedback.show(i18n.t('settings.messaging.modelCatalog.unavailable'), 'warning');
            return;
        }
        const workspaceBrowserAccess = await this.#host.resolveWorkspaceBrowserAccess();
        const result = await openMessagingAccountModal({
            mode: 'create',
            account: null,
            models: this.#models,
            mcpCatalog,
            workspaceBrowserAccess,
            persist: async (payload): Promise<MessagingAccount> => {
                if ('expectedRevision' in payload) throw new TypeError('Messaging create received an update payload');
                return await this.#host.api.create(payload);
            }
        });
        if (!result) return;
        this.#upsertAccount(result);
        this.#showSaveOutcome(result);
    }

    async #editAccount(account: MessagingAccount): Promise<void> {
        const mcpCatalog = this.#requireEditorCatalogs();
        if (!mcpCatalog) return;
        const latest = await this.#host.api.get(account.accountId);
        const workspaceBrowserAccess = await this.#host.resolveWorkspaceBrowserAccess();
        const result = await openMessagingAccountModal({
            mode: 'edit',
            account: latest,
            models: this.#models,
            mcpCatalog,
            workspaceBrowserAccess,
            persist: async (payload): Promise<MessagingAccount> => {
                if (!('expectedRevision' in payload)) throw new TypeError('Messaging edit received a create payload');
                const update: MessagingAccountUpdate = { ...payload, enabled: latest.lifecycleState !== 'disabled' };
                return await this.#host.api.update(latest.accountId, update);
            }
        });
        if (!result) return;
        this.#upsertAccount(result);
        this.#showSaveOutcome(result);
    }

    #buildUpdate(account: MessagingAccount, enabled: boolean): MessagingAccountUpdate {
        return {
            expectedRevision: account.revision,
            label: account.label,
            credentials: null,
            modelSettings: account.modelSettings,
            locale: account.locale,
            enabled,
            plaintextSecretRepliesEnabled: account.plaintextSecretRepliesEnabled,
            replaceExistingCallback: false,
            acceptMessagesFromAnyone: account.acceptMessagesFromAnyone,
            authorizedSenders: account.authorizedSenders
        };
    }

    async #setEnabled(account: MessagingAccount, enabled: boolean): Promise<void> {
        await this.#host.runWithBoundary('settings:messaging:setAccountEnabled', async (): Promise<void> => {
            const updated = await this.#host.api.update(account.accountId, this.#buildUpdate(account, enabled));
            this.#upsertAccount(updated);
            this.#host.feedback.show(enabled ? i18n.t('settings.messaging.notifications.accountEnabled') : i18n.t('settings.messaging.notifications.accountDisabled'), 'success');
        });
    }

    async #deleteAccount(account: MessagingAccount): Promise<void> {
        await this.#host.confirmAndExecute(
            'settings:messaging:removeAccount',
            { title: i18n.t('settings.messaging.confirmRemove.title'), message: i18n.t('settings.messaging.confirmRemove.message'), confirmText: i18n.t('settings.messaging.accounts.actions.remove'), cancelText: i18n.t('common.cancel'), variant: 'danger' },
            async (): Promise<void> => this.#host.api.delete(account.accountId, account.revision),
            i18n.t('settings.messaging.notifications.accountRemoved'),
            (): void => {
                this.#removeAccount(account.accountId);
            },
            null
        );
    }

    #rerender(): void {
        renderSettingsSection({ container: this.#host.pageDom.require('messaging-content'), render: () => this.render(), renderMarkup: (container, markup): void => this.#host.pageDom.updateHtml(container, markup), bind: (): void => this.setupEventListeners(), filter: (): void => this.#host.filterSettings(), hasSearchQuery: (): boolean => this.#host.hasSearchQuery() });
    }
}

export { MessagingManager };
