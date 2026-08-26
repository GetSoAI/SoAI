/* SoAI - Authenticated licensing settings lifecycle and actions [frontend/assets/ts/pages/settings/controllers/LicensingManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingSettingsStatus } from '@core/api/contracts/licensingSettingsContracts.ts';
import type { LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import { licensingLegalAcceptances, type LicensingLegalAcceptanceInput, type LicensingOrganizationInput } from '@core/api/contracts/licensingRequestSerialization.ts';
import { dom, optionalButton, optionalInput, optionalSelect } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError, isAbortError } from '@core/errors/abort.ts';
import { presentLicensingError } from '@core/licensing/errorPresentation.ts';
import { LicensingOperationPollController } from '@core/licensing/operationPollController.ts';
import { i18n } from '@core/i18n/index.ts';
import { showLicenseModal } from '@core/licenseservice/service.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { SettingsSectionLifecycle } from '@features/settings/public.ts';
import type { LicensingManagerHost } from '@pages/settings/contracts/licensingManager.ts';
import { renderLicensingSettings } from '@pages/settings/controllers/licensing/view.ts';

class LicensingManager {
    readonly #host: LicensingManagerHost;
    readonly #lifecycle = new SettingsSectionLifecycle();
    #status: LicensingSettingsStatus | null = null;
    #soaiVersion: string | null = null;
    #mutationIdentity: symbol | null = null;
    #operationPoll: LicensingOperationPollController<LicensingSettingsStatus> | null = null;

    constructor(host: LicensingManagerHost) {
        this.#host = host;
    }

    render(): TrustedHtml {
        return renderLicensingSettings(this.#status, this.#soaiVersion);
    }

    setupEventListeners(): void {
        this.dispose();
        this.#lifecycle.mount();
        this.#operationPoll = new LicensingOperationPollController({
            fetchStatus: (signal) => this.#host.licensing.load({ signal }),
            onStatus: (status) => {
                if (!this.#lifecycle.isMounted) return;
                this.#status = status;
                this.#rerender();
            },
            onFailure: (error) => errorHandler.warn('LicensingManager', 'Licensing operation status poll failed', error)
        });
        this.#bind();
        this.#lifecycle.addCleanup(this.#host.page.subscribeStatusChanged(() => this.#start(this.reload(), 'reload after licensing status event')));
    }

    async reload(): Promise<boolean> {
        const run = this.#lifecycle.beginReload('licensing-reload');
        if (run === null) return false;
        try {
            const [status, soaiVersion] = await Promise.all([this.#host.licensing.load({ signal: run.signal }), this.#loadVersion(run.signal)]);
            if (!this.#lifecycle.isReloadCurrent(run)) return false;
            this.#status = status;
            this.#soaiVersion = soaiVersion;
            this.#rerender();
            this.#operationPoll?.update(status);
            return true;
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(run)) return false;
            errorHandler.warn('LicensingManager', 'Licensing status reload failed', ensureError(error));
            this.#host.page.notify(i18n.t('settings.licensing.reloadFailed'), 'error');
            return false;
        }
    }

    dispose(): void {
        this.#lifecycle.dispose('licensing-dispose');
        this.#operationPoll?.destroy();
        this.#operationPoll = null;
        this.#mutationIdentity = null;
    }

    async #loadVersion(signal: AbortSignal): Promise<string | null> {
        try {
            return await this.#host.system.loadVersion({ signal });
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) throw runtimeError;
            errorHandler.warn('LicensingManager', 'SoAI version is unavailable', runtimeError);
            return null;
        }
    }

    #bind(): void {
        this.#lifecycle.replaceCleanupGroup(
            'licensing-actions',
            () => {
                const container = this.#host.view.requireContainer();
                const clickCleanup = this.#host.view.bindEvent(container, 'click', (event) => this.#handleClick(event));
                const changeCleanup = this.#host.view.bindEvent(container, 'change', (event) => this.#handleChange(event));
                const inputCleanup = this.#host.view.bindEvent(container, 'input', (event) => this.#handleInput(event));
                return [clickCleanup, changeCleanup, inputCleanup].filter((cleanup): cleanup is () => void => cleanup !== null);
            },
            'Licensing settings listener cleanup failed'
        );
    }

    #rerender(): void {
        if (!this.#lifecycle.isMounted) return;
        renderSettingsSection({ container: this.#host.view.requireContainer(), render: () => this.render(), renderMarkup: (container, markup) => this.#host.view.updateHtml(container, markup), bind: () => this.#bind(), filter: () => this.#host.view.filter(), hasSearchQuery: () => this.#host.view.hasSearchQuery() });
    }

    #handleClick(event: Event): void {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const button = target.closest<HTMLButtonElement>('button[data-action]');
        if (!button || this.#status === null) return;
        if (button.dataset.action === 'licensing-review-license') this.#start(showLicenseModal(), 'license review');
        if (button.dataset.action === 'licensing-accept-license')
            this.#start(
                this.#runAction(button, (status, signal) => this.#host.licensing.acceptLicense(status.draftRevision, status.licenseFingerprint, { signal })),
                'license acceptance'
            );
        if (button.dataset.action === 'licensing-activate') this.#start(this.#activate(button), 'activation');
        if (button.dataset.action === 'licensing-convert-os-evaluation') this.#start(this.#convertOsEvaluation(button), 'OS evaluation conversion');
        if (button.dataset.action === 'licensing-revert-os-evaluation') this.#start(this.#revertOsEvaluation(button), 'OS evaluation reversion');
        if (button.dataset.action === 'licensing-convert-commercial') this.#start(this.#convertCommercial(button), 'commercial conversion');
        if (button.dataset.action === 'licensing-reclassify') this.#start(this.#reclassify(button), 'deployment reclassification');
        if (button.dataset.action === 'licensing-retrieve-term')
            this.#start(
                this.#runAction(button, (status, signal) => this.#host.licensing.retrieveTerm(status.draftRevision, { signal })),
                'term retrieval'
            );
        if (button.dataset.action === 'licensing-reconcile') this.#start(this.#reconcile(button), 'operation reconciliation');
        if (button.dataset.action === 'licensing-export-offline') this.#start(this.#exportOffline(button), 'offline request export');
        if (button.dataset.action === 'licensing-import-offline') optionalInput(dom.resolve('#settings-offline-certificate', this.#host.view.requireContainer()), 'Licensing offline certificate input')?.click();
        if (button.dataset.action === 'licensing-deactivate') this.#start(this.#deactivate(button), 'deactivation');
        if (button.dataset.action === 'licensing-declare-personal') this.#start(this.#declarePersonal(button), 'personal declaration');
        if (button.dataset.action === 'licensing-declare-organization')
            this.#start(
                this.#runAction(button, (status, signal) => this.#host.licensing.changeDeclaration(status.draftRevision, 'organization_commercial', { confirmed: false, revision: null }, { signal })),
                'organization declaration'
            );
        if (button.dataset.action === 'licensing-open-power') this.#start(this.#host.page.openPowerPage(), 'open Power page');
    }

    #handleChange(event: Event): void {
        const source = event.target;
        if (!(source instanceof HTMLInputElement)) return;
        if (source.id !== 'settings-offline-certificate' || this.#status === null) return;
        const file = source.files?.[0] ?? null;
        source.value = '';
        if (file)
            this.#start(
                this.#runAction(source, (status, signal) => this.#host.licensing.importOffline(status.draftRevision, file, { signal })),
                'offline entitlement import'
            );
    }

    #handleInput(event: Event): void {
        const source = event.target;
        if (!(source instanceof HTMLInputElement)) return;
        if (source.id === 'settings-license-key') {
            const button = optionalButton(dom.resolve('[data-action="licensing-activate"]', this.#host.view.requireContainer()), 'Licensing activation button');
            if (button) button.disabled = source.value.length < 16;
        }
        if (source.id === 'settings-commercial-key') {
            const button = optionalButton(dom.resolve('[data-action="licensing-convert-commercial"]', this.#host.view.requireContainer()), 'Licensing commercial conversion button');
            if (button) button.disabled = source.value.length < 16;
        }
        if (source.id.startsWith('settings-organization-') || source.id.startsWith('settings-authorized-')) {
            const button = optionalButton(dom.resolve('[data-action="licensing-convert-os-evaluation"]', this.#host.view.requireContainer()), 'Licensing OS evaluation conversion button');
            if (button) button.disabled = this.#organizationInput() === null;
        }
    }

    async #activate(button: HTMLButtonElement): Promise<void> {
        const input = optionalInput(dom.resolve('#settings-license-key', this.#host.view.requireContainer()), 'Licensing product key input');
        const commercialEnvironment = this.#initialCommercialEnvironment();
        let productKey = input?.value ?? '';
        if (input) input.value = '';
        button.disabled = true;
        if (productKey.length < 16 || this.#status === null || (this.#status.declaration === 'organization_commercial' && commercialEnvironment === null)) return;
        await this.#runAction(button, async (status, signal) => {
            try {
                const flow: LicensingLegalFlow = status.edition === 'soai-os' && status.declaration === 'personal' ? 'personal_os_activation' : 'commercial_activation';
                const acceptances = await this.#acceptDocuments(flow, signal);
                const deploymentEnvironment = flow === 'commercial_activation' ? commercialEnvironment : null;
                return this.#host.licensing.activate(status.draftRevision, { activationCredential: productKey, deploymentEnvironment, legalAcceptances: acceptances }, { signal });
            } finally {
                productKey = '';
            }
        });
    }

    async #exportOffline(button: HTMLButtonElement): Promise<void> {
        const status = this.#status;
        if (status === null) return;
        const deploymentEnvironment = status.entitlement?.deploymentEnvironment ?? (status.declaration === 'organization_commercial' ? this.#initialCommercialEnvironment() : null);
        if (status.declaration === 'organization_commercial' && deploymentEnvironment === null) return;
        await this.#runAction(button, (currentStatus, signal) => this.#host.licensing.exportOffline(currentStatus.draftRevision, deploymentEnvironment, { signal }));
    }

    #initialCommercialEnvironment(): 'production' | 'non_production' | null {
        const value = optionalSelect(dom.resolve('#settings-activation-environment', this.#host.view.requireContainer()), 'Licensing activation environment')?.value;
        return value === 'production' || value === 'non_production' ? value : null;
    }

    async #reconcile(button: HTMLButtonElement): Promise<void> {
        if (this.#status === null) return;
        await this.#runAction(button, (status, signal) => this.#host.licensing.reconcile(status.draftRevision, { signal }));
    }

    async #convertOsEvaluation(button: HTMLButtonElement): Promise<void> {
        const organization = this.#organizationInput();
        if (organization === null) return;
        await this.#runAction(button, async (status, signal) => this.#host.licensing.convertOsEvaluation(status.draftRevision, organization, await this.#acceptDocuments('os_evaluation_conversion', signal), { signal }));
    }

    async #revertOsEvaluation(button: HTMLButtonElement): Promise<void> {
        const confirmed = await requireDialogsService().showConfirmation({ title: i18n.t('settings.licensing.revertOsEvaluation'), message: i18n.t('settings.licensing.revertOsEvaluationConfirm'), confirmText: i18n.t('settings.licensing.revertOsEvaluation'), cancelText: i18n.t('common.cancel'), variant: 'warning' });
        if (!confirmed) return;
        await this.#runAction(button, (status, signal) => this.#host.licensing.revertOsEvaluation(status.draftRevision, { signal }));
    }

    async #convertCommercial(button: HTMLButtonElement): Promise<void> {
        const input = optionalInput(dom.resolve('#settings-commercial-key', this.#host.view.requireContainer()), 'Licensing commercial credential input');
        const environment = optionalSelect(dom.resolve('#settings-commercial-environment', this.#host.view.requireContainer()), 'Licensing commercial environment')?.value;
        let activationCredential = input?.value ?? '';
        if (input) input.value = '';
        button.disabled = true;
        if (activationCredential.length < 16 || (environment !== 'production' && environment !== 'non_production')) return;
        await this.#runAction(button, async (status, signal) => {
            try {
                return this.#host.licensing.convertCommercial(status.draftRevision, { activationCredential, deploymentEnvironment: environment, legalAcceptances: await this.#acceptDocuments('commercial_activation', signal) }, { signal });
            } finally {
                activationCredential = '';
            }
        });
    }

    async #reclassify(button: HTMLButtonElement): Promise<void> {
        const environment = optionalSelect(dom.resolve('#settings-reclassification-environment', this.#host.view.requireContainer()), 'Licensing reclassification environment')?.value;
        if (environment !== 'production' && environment !== 'non_production') return;
        await this.#runAction(button, (status, signal) => this.#host.licensing.reclassify(status.draftRevision, environment, { signal }));
    }

    async #acceptDocuments(flow: LicensingLegalFlow, signal: AbortSignal): Promise<LicensingLegalAcceptanceInput[]> {
        const documents = await this.#host.licensing.governingDocuments(flow, { signal });
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('settings.licensing.legalAcceptanceTitle'),
            message: documents.documents.map((document) => `${document.documentName} ${document.version}\n${document.fingerprint}\n\n${document.licenseText}`).join('\n\n──────────\n\n'),
            description: i18n.t('settings.licensing.legalAcceptanceDescription'),
            confirmText: i18n.t('settings.licensing.acceptAndActivate'),
            cancelText: i18n.t('common.cancel')
        });
        if (!confirmed) throw createAbortError('Licensing legal acceptance cancelled');
        return licensingLegalAcceptances(documents);
    }

    #organizationInput(): LicensingOrganizationInput | null {
        const value = (id: string): string => optionalInput(dom.resolve(`#${id}`, this.#host.view.requireContainer()), `Licensing ${id} input`)?.value ?? '';
        const legalName = value('settings-organization-legal-name');
        const countryCode = value('settings-organization-country');
        const registrationOrTaxId = value('settings-organization-tax-id');
        const authorizedAcceptorName = value('settings-authorized-acceptor-name');
        const authorizedAcceptorEmail = value('settings-authorized-acceptor-email');
        if (!legalName || !/^[A-Z]{2}$/.test(countryCode) || !registrationOrTaxId || !authorizedAcceptorName || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(authorizedAcceptorEmail)) return null;
        return { legalName, countryCode, registrationOrTaxId, authorizedAcceptorName, authorizedAcceptorEmail, authorityAttested: true };
    }

    async #runAction(control: HTMLElement, operation: (status: LicensingSettingsStatus, signal: AbortSignal) => Promise<LicensingSettingsStatus>): Promise<void> {
        if (this.#mutationIdentity !== null || this.#status === null) return;
        const currentStatus = this.#status;
        const run = this.#lifecycle.beginReload('licensing-action');
        if (run === null) return;
        const mutationIdentity = Symbol('licensing-action');
        this.#mutationIdentity = mutationIdentity;
        if (control instanceof HTMLButtonElement) beginLoadingButton(control);
        try {
            const status = await operation(currentStatus, run.signal);
            if (!this.#lifecycle.isReloadCurrent(run)) return;
            this.#status = status;
            this.#rerender();
            this.#operationPoll?.update(status);
            this.#host.page.notify(i18n.t('settings.licensing.updated'), 'success');
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(run)) return;
            if (isAbortError(error)) return;
            this.#host.page.notify(presentLicensingError(ensureError(error)), 'error');
        } finally {
            if (this.#mutationIdentity === mutationIdentity) this.#mutationIdentity = null;
            if (control instanceof HTMLButtonElement) clearLoadingButtonIfNeeded(control);
        }
    }

    async #deactivate(button: HTMLButtonElement): Promise<void> {
        const reason = optionalSelect(dom.resolve('#settings-licensing-deactivation-reason', this.#host.view.requireContainer()), 'Licensing deactivation reason')?.value;
        if (reason !== 'rehost' && reason !== 'retired' && reason !== 'disaster_recovery' && reason !== 'other') return;
        if (!(await this.#host.page.confirmDeactivation())) return;
        await this.#runAction(button, (_status, signal) => this.#host.licensing.deactivate(reason, { signal }));
    }

    async #declarePersonal(button: HTMLButtonElement): Promise<void> {
        const status = this.#status;
        if (status === null) return;
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('settings.licensing.personalAttestationConfirmTitle'),
            message: status.personalAttestationText,
            description: i18n.t('settings.licensing.personalAttestationConfirmDescription'),
            confirmText: i18n.t('settings.licensing.declarePersonal'),
            cancelText: i18n.t('common.cancel'),
            variant: 'warning'
        });
        if (!confirmed) return;
        await this.#runAction(button, (status, signal) => this.#host.licensing.changeDeclaration(status.draftRevision, 'personal', { confirmed: true, revision: status.personalAttestationRevision }, { signal }));
    }

    #start(operation: Promise<boolean | void>, context: string): void {
        void operation.catch((error) => {
            errorHandler.error('LicensingManager', `Licensing ${context} failed outside its action boundary`, ensureError(error));
        });
    }
}

export { LicensingManager };
