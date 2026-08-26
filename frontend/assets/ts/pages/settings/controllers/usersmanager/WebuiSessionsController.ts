/* SoAI - Settings page WebUI sessions controller [frontend/assets/ts/pages/settings/controllers/usersmanager/WebuiSessionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { executeConfirmedButtonAction } from '@pages/settings/controllers/page/confirmedactionexecution/service.ts';
import type { UsersManagerHost } from '@pages/settings/controllers/usersmanager/types.ts';
import { isSessionsActionId, renderSessionsContent, SESSIONS_ACTION_REVOKE, SESSIONS_ACTION_REVOKE_ALL } from '@pages/settings/controllers/usersmanager/WebuiSessions.ts';

class WebuiSessionsController {
    readonly #host: UsersManagerHost;
    #abortController: AbortController | null = null;
    #sequence = 0;
    #mutationInFlight = false;

    constructor(host: UsersManagerHost) {
        this.#host = host;
    }

    mount(container: HTMLElement): void {
        this.destroy();
        const abortController = new AbortController();
        this.#abortController = abortController;
        const subgroup = this.#host.view.pageDom.requireHTMLElement('webui-sessions-subgroup', container);
        this.#host.view.pageDom.requireHTMLElement('webui-sessions-list', subgroup);
        const revokeAllButton = narrowButton(this.#host.view.pageDom.requireHTMLElement('webui-sessions-revoke-all-btn', subgroup), 'Revoke all sessions button');
        if (requireTrimmedDataAttribute(revokeAllButton, 'action', 'Revoke all sessions button') !== SESSIONS_ACTION_REVOKE_ALL) {
            throw new Error('Revoke all sessions button is missing required data-action');
        }
        bindDataActionListener({
            root: subgroup,
            eventType: 'click',
            signal: abortController.signal,
            isAction: isSessionsActionId,
            preventDefault: 'always',
            mouseButton: 'primary',
            ignoreDisabled: true,
            onAction: async ({ action, actionElement }): Promise<void> => {
                await this.#host.execution.runWithBoundary('settings:webuiSessions', async (): Promise<void> => {
                    if (action === SESSIONS_ACTION_REVOKE_ALL) {
                        await this.#revokeAll(actionElement);
                        return;
                    }
                    if (action === SESSIONS_ACTION_REVOKE) {
                        await this.#revoke(actionElement);
                    }
                });
            }
        });
        this.#startRefresh();
    }

    async refresh(): Promise<boolean> {
        const abortController = this.#abortController;
        if (abortController === null) {
            return false;
        }
        const sequence = ++this.#sequence;
        const sessions = await this.#host.api.listSessions({ signal: abortController.signal });
        if (abortController.signal.aborted || sequence !== this.#sequence) {
            return false;
        }
        const list = this.#host.view.pageDom.requireHTMLElement('webui-sessions-list');
        this.#host.view.pageDom.updateHtml(list, toTrustedUiHtml(renderSessionsContent(sessions)));
        this.#host.filterSettings();
        return true;
    }

    destroy(): void {
        this.#sequence += 1;
        this.#abortController?.abort('webui-sessions-destroy');
        this.#abortController = null;
    }

    #startRefresh(): void {
        const abortController = this.#abortController;
        void this.refresh().catch((error) => {
            if (abortController === null || abortController.signal.aborted) {
                return;
            }
            errorHandler.warn('WebuiSessionsController', 'Active session refresh failed', ensureError(error));
            this.#host.notifications.feedback.show(i18n.t('settings.users.sessions.loadFailed'), 'error');
        });
    }

    async #revoke(actionElement: HTMLElement): Promise<void> {
        if (this.#abortController === null || this.#mutationInFlight) {
            return;
        }
        const button = narrowButton(actionElement, 'Session revoke button');
        const jti = requireTrimmedDataAttribute(actionElement, 'jti', 'Session revoke button');
        const current = requireTrimmedDataAttribute(actionElement, 'current', 'Session revoke button');
        if (current !== 'true' && current !== 'false') {
            throw new Error('Session revoke button has invalid current-session state');
        }
        this.#mutationInFlight = true;
        try {
            await executeConfirmedButtonAction({
                host: this.#host.execution,
                button,
                boundaryName: 'settings:revokeWebuiSession',
                confirmOptions: {
                    title: i18n.t('settings.users.sessions.confirm.title'),
                    message: i18n.t('settings.users.sessions.confirm.message'),
                    confirmText: i18n.t('settings.users.sessions.revoke'),
                    cancelText: i18n.t('common.cancel'),
                    variant: 'danger'
                },
                action: () => this.#host.api.revokeSession(jti),
                successMessage: i18n.t('settings.users.sessions.revoked'),
                afterSuccess: async (): Promise<void> => {
                    if (current === 'true') {
                        await this.#host.api.invalidateSession();
                        return;
                    }
                    await this.refresh();
                }
            });
        } finally {
            this.#mutationInFlight = false;
        }
    }

    async #revokeAll(actionElement: HTMLElement): Promise<void> {
        if (this.#abortController === null || this.#mutationInFlight) {
            return;
        }
        const button = narrowButton(actionElement, 'Revoke all sessions button');
        this.#mutationInFlight = true;
        try {
            await executeConfirmedButtonAction({
                host: this.#host.execution,
                button,
                boundaryName: 'settings:revokeAllWebuiSessions',
                confirmOptions: {
                    title: i18n.t('settings.users.sessions.revokeAll.confirmTitle'),
                    message: i18n.t('settings.users.sessions.revokeAll.confirmMessage'),
                    confirmText: i18n.t('settings.users.sessions.revokeAll.button'),
                    cancelText: i18n.t('common.cancel'),
                    variant: 'danger'
                },
                action: async (): Promise<null> => {
                    await this.#host.api.revokeAllSessions();
                    await this.#host.api.invalidateSession();
                    return null;
                }
            });
        } finally {
            this.#mutationInFlight = false;
        }
    }
}

export { WebuiSessionsController };
