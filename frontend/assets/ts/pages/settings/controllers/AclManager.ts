/* SoAI - Settings page acl manager [frontend/assets/ts/pages/settings/controllers/AclManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedDataAttribute, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { markSettingsCapabilityFailed, markSettingsCapabilityReady, SettingsSectionLifecycle } from '@features/settings/public.ts';
import { areAclOverridesEqual, collectAclActionCheckboxes, computeAclOverrides, normalizeAclOverrides } from '@pages/settings/controllers/aclpolicyoverrides/service.ts';
import { createAclActionFieldKey, renderAclManagerMarkup } from '@pages/settings/controllers/aclManagerMarkup.ts';
import type { AclManagerAvailabilityPort, AclManagerDependencies, AclManagerHost } from '@pages/settings/controllers/AclManagerSupport.ts';

class AclManager {
    readonly #host: AclManagerHost;
    readonly #availability: AclManagerAvailabilityPort;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();
    constructor({ host, availability }: AclManagerDependencies) {
        if (!host || !availability) {
            throw new Error('AclManager requires host and availability ports');
        }
        this.#host = host;
        this.#availability = availability;
    }

    render(): TrustedHtml {
        return renderAclManagerMarkup(this.#host, this.#availability.get());
    }

    hasChanges(): boolean {
        if (!this.#lifecycle.isMounted || !this.#host.isAdmin()) {
            return false;
        }
        const policy = this.#host.getAclPolicy();
        if (!policy) {
            return false;
        }
        const root = this.#host.pageDom.optionalHTMLElement ? this.#host.pageDom.optionalHTMLElement('acl-content') : null;
        if (!root) {
            return false;
        }
        const next = normalizeAclOverrides(computeAclOverrides(root, policy));
        const current = normalizeAclOverrides(policy.overrides);
        return !areAclOverridesEqual(current, next);
    }

    setupEventListeners(): void {
        this.dispose();
        if (!this.#host.isAdmin()) return;
        this.#lifecycle.mount();
        const root = this.#requireHTMLElement('acl-content');
        this.#syncAllActionDirtyStates(root);
        this.#lifecycle.addCleanup(
            this.#host.pageResources.on(root, 'change', (eventObject: Event) => {
                try {
                    this.#handleRootChange(root, eventObject);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    this.#host.feedback.handle(runtimeError, 'ACL change dispatch');
                    throw runtimeError;
                }
            })
        );
    }

    dispose(): void {
        this.#lifecycle.dispose('acl-dispose');
    }

    async reload(): Promise<void> {
        const reloadRun = this.#lifecycle.beginReload('acl-reload');
        if (reloadRun === null) {
            return;
        }
        try {
            const policy = await this.#host.getPolicy();
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return;
            }
            this.#host.setAclPolicy(policy);
            this.#availability.set(markSettingsCapabilityReady());
            this.#renderAndBindContent();
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return;
            }
            this.#availability.set(markSettingsCapabilityFailed(this.#availability.get()));
            this.#renderAndBindContent();
            this.#host.feedback.handle(ensureError(error), 'ACL policy reload');
            this.#host.feedback.show(i18n.t('settings.acl.errors.reloadFailed'), 'error');
        }
    }

    async savePolicy(): Promise<void> {
        return this.#host.runWithBoundary('settings:saveAclPolicy', async () => {
            if (!this.#host.isAdmin()) {
                return;
            }
            const root = this.#requireHTMLElement('acl-content');
            const policy = this.#host.getAclPolicy();
            if (!policy) {
                return;
            }
            const nextOverrides = normalizeAclOverrides(computeAclOverrides(root, policy));
            const currentOverrides = normalizeAclOverrides(policy.overrides);
            if (areAclOverridesEqual(currentOverrides, nextOverrides)) {
                return;
            }
            await this.#host.updatePolicy(nextOverrides);
            const refreshed = await this.#host.getPolicy();
            this.#host.setAclPolicy(refreshed);
            this.#availability.set(markSettingsCapabilityReady());
            this.#syncCheckboxDefaults(root);
            this.#syncAllActionDirtyStates(root);
            this.#host.feedback.show(i18n.t('settings.acl.notifications.saveSuccess'), 'success');
            this.#host.notifySaveChanged();
            dispatchCustomEvent('soai:search:request-refresh', {});
        });
    }

    #handleRootChange(root: HTMLElement, eventObject: Event): void {
        const target = eventObject.target;
        if (!(target instanceof HTMLInputElement)) {
            return;
        }
        if (target.type !== 'checkbox') {
            return;
        }
        if (!root.contains(target)) {
            return;
        }
        if (!optionalTrimmedDataAttribute(target, 'aclAction')) {
            return;
        }
        if (target.disabled) {
            return;
        }
        this.#host.updatePreferenceToggleLabel(target, target.checked);
        const role = requireTrimmedDataAttribute(target, 'aclRole', 'ACL action checkbox');
        const action = requireTrimmedDataAttribute(target, 'aclAction', 'ACL action checkbox');
        this.#host.syncManualDirtyField(createAclActionFieldKey(role, action), target.checked !== target.defaultChecked, true);
        this.#host.notifySaveChanged();
    }

    #syncAllActionDirtyStates(root: HTMLElement): void {
        for (const checkbox of collectAclActionCheckboxes(root)) {
            const role = requireTrimmedDataAttribute(checkbox, 'aclRole', 'ACL action checkbox');
            const action = requireTrimmedDataAttribute(checkbox, 'aclAction', 'ACL action checkbox');
            this.#host.syncManualDirtyField(createAclActionFieldKey(role, action), checkbox.checked !== checkbox.defaultChecked, true);
        }
    }

    #syncCheckboxDefaults(root: HTMLElement): void {
        for (const checkbox of collectAclActionCheckboxes(root)) {
            checkbox.defaultChecked = checkbox.checked;
        }
    }

    #renderAndBindContent(): void {
        renderSettingsSection({
            container: this.#requireElement('acl-content'),
            render: () => this.render(),
            renderMarkup: (container, markup): void => this.#host.pageDom.updateHtml(container, markup),
            bind: (): void => this.setupEventListeners(),
            filter: (): void => this.#host.filterSettings(),
            hasSearchQuery: (): boolean => this.#host.hasSearchQuery()
        });
    }

    #requireElement(selector: string, context?: Element): Element {
        return this.#host.pageDom.require(selector, context);
    }

    #requireHTMLElement(selector: string, context?: Element): HTMLElement {
        return narrowHTMLElement(this.#requireElement(selector, context), `ACL element "${selector}"`);
    }
}
export { AclManager };
