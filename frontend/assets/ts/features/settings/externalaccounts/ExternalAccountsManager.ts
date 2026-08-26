/* SoAI - Settings feature external accounts manager [frontend/assets/ts/features/settings/externalaccounts/ExternalAccountsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { CalendarAccountEntry, ExternalAccountType, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';
import { SettingsSectionLifecycle } from '@features/settings/sectionLifecycle.ts';
import { createSettingsCapabilityAvailability, markSettingsCapabilityFailed, markSettingsCapabilityReady, settleSettingsCapability, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';
import { EXTERNAL_ACCOUNTS_ACTION_ADD, EXTERNAL_ACCOUNTS_ACTION_MANAGE, isExternalAccountsActionId, type ExternalAccountsActionId } from '@features/settings/externalaccounts/actionIds.ts';
import { requireRoot } from '@features/settings/externalaccounts/dom.ts';
import { openExternalAccountModal } from '@features/settings/externalaccounts/externalAccountModal.ts';
import { syncExternalAccountsRenderedState } from '@features/settings/externalaccounts/renderState.ts';
import type { ExternalAccountsManagerDependencies, ExternalAccountsManagerHost } from '@features/settings/externalaccounts/types.ts';
import { renderExternalAccountsSection } from '@features/settings/externalaccounts/view.ts';

class ExternalAccountsManager {
    readonly #host: ExternalAccountsManagerHost;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();
    #mailAccounts: MailAccountEntry[] = [];
    #calendarAccounts: CalendarAccountEntry[] = [];
    #mailAvailability: SettingsCapabilityAvailability = createSettingsCapabilityAvailability();
    #calendarAvailability: SettingsCapabilityAvailability = createSettingsCapabilityAvailability();

    constructor({ host }: ExternalAccountsManagerDependencies) {
        this.#host = host;
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(renderExternalAccountsSection(this.#mailAvailability, this.#calendarAvailability));
    }

    setupEventListeners(): void {
        this.#lifecycle.mount();
        const root = requireRoot(this.#host);
        bindPageActionDispatcher({
            label: 'External accounts settings',
            root,
            signal: this.#lifecycle.createAbortSignal('external-accounts-actions-dispose'),
            isAction: isExternalAccountsActionId,
            events: {
                click: {
                    preventDefault: 'interactive',
                    mouseButton: 'primary',
                    ignoreDisabled: true,
                    onAction: async ({ action, actionElement }): Promise<void> => await this.#handleAction(action, actionElement)
                }
            }
        });
    }

    dispose(): void {
        this.#lifecycle.dispose('external-accounts-dispose');
    }

    async reload(options: { showFailureNotification?: boolean } = {}): Promise<boolean> {
        const reloadRun = this.#lifecycle.beginReload('external-accounts-reload');
        if (reloadRun === null) {
            return false;
        }
        try {
            const [mailResult, calendarResult] = await Promise.all([settleSettingsCapability(() => this.#host.api.webui.mail.accounts.list()), settleSettingsCapability(() => this.#host.api.webui.calendar.accounts.list())]);
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return false;
            }
            if (mailResult.succeeded && mailResult.value) {
                this.#mailAccounts = mailResult.value;
                this.#mailAvailability = markSettingsCapabilityReady();
            } else {
                this.#mailAvailability = markSettingsCapabilityFailed(this.#mailAvailability);
                this.#reportReloadFailure(mailResult.error, 'mail');
            }
            if (calendarResult.succeeded && calendarResult.value) {
                this.#calendarAccounts = calendarResult.value;
                this.#calendarAvailability = markSettingsCapabilityReady();
            } else {
                this.#calendarAvailability = markSettingsCapabilityFailed(this.#calendarAvailability);
                this.#reportReloadFailure(calendarResult.error, 'calendar');
            }
            syncExternalAccountsRenderedState({
                host: this.#host,
                mailAccounts: this.#mailAccounts,
                calendarAccounts: this.#calendarAccounts,
                mailAvailability: this.#mailAvailability,
                calendarAvailability: this.#calendarAvailability
            });
            const succeeded = mailResult.succeeded && calendarResult.succeeded;
            if (!succeeded && options.showFailureNotification !== false) {
                this.#host.feedback.show(i18n.t('settings.externalAccounts.errors.reloadFailed'), 'error');
            }
            return succeeded;
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return false;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('ExternalAccountsManager', 'External accounts reload failed', runtimeError);
            if (options.showFailureNotification !== false) {
                this.#host.feedback.show(i18n.t('settings.externalAccounts.errors.reloadFailed'), 'error');
            }
            return false;
        }
    }

    #reportReloadFailure(error: Error | null, capability: 'mail' | 'calendar'): void {
        const runtimeError = error ?? new Error(`External ${capability} accounts reload failed`);
        this.#host.feedback.handle(runtimeError, `External ${capability} accounts reload`, { severity: 'warn' });
    }

    async #handleAction(action: ExternalAccountsActionId, actionElement: HTMLElement): Promise<void> {
        if (action === EXTERNAL_ACCOUNTS_ACTION_ADD) {
            await this.#openModal({ mode: 'launcher' });
            return;
        }
        if (action !== EXTERNAL_ACCOUNTS_ACTION_MANAGE) {
            throw new Error(i18n.t('settings.externalAccounts.errors.actionFailed'));
        }
        const accountType = this.#readActionAccountType(actionElement);
        const accountId = this.#readActionAccountId(actionElement);
        const account = accountType === 'mail' ? this.#findMailAccount(accountId) : this.#findCalendarAccount(accountId);
        if (account === null) {
            throw new Error(i18n.t('settings.externalAccounts.errors.actionFailed'));
        }
        await this.#openModal({
            mode: 'edit',
            accountType,
            account
        });
    }

    #readActionAccountType(actionElement: HTMLElement): ExternalAccountType {
        const accountType = requireTrimmedDataAttribute(actionElement, 'accountType', 'External account action');
        if (accountType === 'mail' || accountType === 'calendar') {
            return accountType;
        }
        throw new Error(i18n.t('settings.externalAccounts.errors.actionFailed'));
    }

    #readActionAccountId(actionElement: HTMLElement): string {
        return requireTrimmedDataAttribute(actionElement, 'accountId', 'External account action');
    }

    async #openModal(inputArguments: { mode: 'launcher' | 'create' | 'edit'; accountType?: 'mail' | 'calendar'; account?: MailAccountEntry | CalendarAccountEntry }): Promise<void> {
        try {
            await openExternalAccountModal({
                host: this.#host,
                mode: inputArguments.mode,
                ...(inputArguments.accountType ? { accountType: inputArguments.accountType } : {}),
                ...(inputArguments.account ? { account: inputArguments.account } : {}),
                getMailAccounts: () => this.#mailAccounts.slice(),
                findMailAccount: (accountId: string) => this.#findMailAccount(accountId),
                findCalendarAccount: (accountId: string) => this.#findCalendarAccount(accountId),
                reload: async () => await this.reload({ showFailureNotification: false })
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#host.feedback.handle(runtimeError, 'External accounts modal');
        }
    }

    #findMailAccount(accountId: string | null): MailAccountEntry | null {
        return accountId ? (this.#mailAccounts.find((account) => account.accountId === accountId) ?? null) : null;
    }

    #findCalendarAccount(accountId: string | null): CalendarAccountEntry | null {
        return accountId ? (this.#calendarAccounts.find((account) => account.accountId === accountId) ?? null) : null;
    }
}

export { ExternalAccountsManager };
