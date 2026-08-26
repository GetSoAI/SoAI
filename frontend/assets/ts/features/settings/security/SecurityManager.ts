/* SoAI - Settings security audit manager [frontend/assets/ts/features/settings/security/SecurityManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { SettingsSectionLifecycle } from '@features/settings/sectionLifecycle.ts';
import { markSettingsCapabilityFailed, markSettingsCapabilityReady } from '@features/settings/capabilityAvailability.ts';
import { SECURITY_ACTION_OPEN_USERS } from '@features/settings/security/actions.ts';
import type { SecurityManagerDependencies, SecurityManagerHost } from '@features/settings/security/types.ts';
import { renderSecurityAudit } from '@features/settings/security/view.ts';

const SECURITY_CONTAINER_ID = 'security-content';
const SECURITY_CLEANUP_GROUP = 'security-audit-listeners';
const SECURITY_CLEANUP_ERROR = 'Security audit listener cleanup failed';

class SecurityManager {
    readonly #host: SecurityManagerHost;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();

    constructor({ host }: SecurityManagerDependencies) {
        if (!host) {
            throw new Error('SecurityManager requires a host instance');
        }
        this.#host = host;
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(renderSecurityAudit(this.#host.getSecurityAudit(), this.#host.getCoreConfig(), this.#host.getSecurityAvailability()));
    }

    setupEventListeners(): void {
        this.dispose();
        this.#lifecycle.mount();
        this.#bindContainerHandlers();
    }

    async reload(): Promise<boolean> {
        const reloadRun = this.#lifecycle.beginReload('security-reload');
        if (reloadRun === null) {
            return false;
        }
        try {
            const payload = await this.#host.loadSecurityAudit({ signal: reloadRun.signal });
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return false;
            }
            this.#host.setSecurityAudit(payload);
            this.#host.setSecurityAvailability(markSettingsCapabilityReady());
            this.#renderIntoContainer();
            return true;
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return false;
            }
            const runtimeError = ensureError(error);
            this.#host.setSecurityAvailability(markSettingsCapabilityFailed(this.#host.getSecurityAvailability()));
            this.#renderIntoContainer();
            errorHandler.warn('SecurityManager', 'Security audit reload failed', runtimeError);
            this.#host.feedback.show(i18n.t('settings.security.errors.reloadFailed'), 'error');
            return false;
        }
    }

    dispose(): void {
        this.#lifecycle.dispose('security-dispose');
    }

    #renderIntoContainer(): void {
        if (!this.#lifecycle.isMounted) {
            return;
        }
        renderSettingsSection({
            container: this.#requireContainer(),
            render: () => this.render(),
            renderMarkup: (container, markup): void => this.#host.pageDom.updateHtml(container, markup),
            afterRender: (): void => this.#host.rebindConfigForm(),
            bind: (): void => this.#bindContainerHandlers(),
            filter: (): void => this.#host.filterSettings(),
            hasSearchQuery: (): boolean => this.#host.hasSearchQuery()
        });
    }

    #bindContainerHandlers(): void {
        const container = this.#requireContainer();
        this.#lifecycle.replaceCleanupGroup(
            SECURITY_CLEANUP_GROUP,
            () => {
                const cleanup = this.#host.pageResources.on(container, 'click', (event) => {
                    this.#handleClick(event);
                });
                return cleanup ? [cleanup] : [];
            },
            SECURITY_CLEANUP_ERROR
        );
    }

    #handleClick(event: Event): void {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const actionElement = target.closest('[data-action]');
        if (!(actionElement instanceof HTMLElement)) {
            return;
        }
        const action = actionElement.dataset.action ?? '';
        if (action === SECURITY_ACTION_OPEN_USERS) {
            event.preventDefault();
            this.#host.openUsersTab();
        }
    }

    #requireContainer(): Element {
        return this.#host.pageDom.require(SECURITY_CONTAINER_ID);
    }
}

export { SecurityManager };
