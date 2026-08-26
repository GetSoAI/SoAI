/* SoAI - Wizard UI coordination [frontend/assets/ts/pages/wizard/controllers/wizardUiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom, optionalInput } from '@core/dom/dom.ts';
import { narrowInput } from '@core/dom/narrowElement.ts';
import { buildLanguageOptions } from '@core/languageservice/languageOptions.ts';
import { isLicensingOperationInProgress } from '@core/licensing/operationLifecycle.ts';
import { resolveBrowserCountryCode } from '@core/localization/public.ts';
import { normalizeProgressRatio } from '@core/primitives/progress.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { LanguageEntryWithFlag } from '@core/languageservice/types.ts';
import { syncDeterminateProgress } from '@core/ui/progressWidths.ts';
import { getTooltipText, setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { syncAttributeValue } from '@core/dom/patching.ts';
import type { WizardState, WizardStepId } from '@features/wizard/public.ts';
import { requireWizardAccountUi, requireWizardUi } from '@pages/wizard/dom.ts';
import { isWizardAccountFormEligibleForSubmit } from '@pages/wizard/guards/validation.ts';
import type { ProductAccessFlow, WizardAccountUi, WizardUi, WizardViewContext } from '@pages/wizard/types.ts';

interface WizardLanguageService {
    getLanguage: () => string;
    getAvailableLanguages: () => ReadonlyArray<LanguageEntryWithFlag>;
}

interface WizardPageUiDependencies {
    readonly state: WizardState;
    requireHTMLElement: (selector: string, context?: ParentNode) => HTMLElement;
    updateStyle: (element: HTMLElement, property: string, value: string) => void;
    toggleClassName: (element: HTMLElement, className: string, value: boolean) => void;
    updateText: (element: HTMLElement, value: string) => void;
    toggleHidden: (element: HTMLElement, hidden: boolean) => void;
    updateProperty: (element: HTMLElement, property: string, value: boolean) => void;
    updateAttribute: (element: HTMLElement, attribute: string, value: string | null) => void;
    getIconSync: (name: string, options: { width: number; height: number }) => TrustedHtml;
    sanitizer: {
        html: (value: string) => string;
        attribute: (value: string) => string;
    };
    languageService: WizardLanguageService;
}

interface ProductAccessNavigation {
    action: 'wizard-activate' | 'wizard-activate-evaluation' | 'wizard-export-offline' | 'wizard-next' | 'wizard-start-evaluation';
    disabled: boolean;
    label: string;
    reason: string;
}

const productAccessFlow = (value: string): ProductAccessFlow | null => {
    if (value === 'evaluation' || value === 'online_activation' || value === 'offline_activation') return value;
    return null;
};

class WizardPageUiController {
    readonly #dependencies: WizardPageUiDependencies;

    #ui: WizardUi | null = null;

    constructor(dependencies: WizardPageUiDependencies) {
        this.#dependencies = dependencies;
    }

    reset(): void {
        this.#ui = null;
    }

    ensureUi(): WizardUi {
        if (this.#ui) {
            return this.#ui;
        }

        this.#ui = requireWizardUi(this.#dependencies);
        return this.#ui;
    }

    requireAccountUi(): WizardAccountUi {
        return requireWizardAccountUi(this.#dependencies);
    }

    createViewContext(): WizardViewContext {
        const currentLanguageValue = this.#dependencies.languageService.getLanguage();
        if (typeof currentLanguageValue !== 'string' || !currentLanguageValue.trim()) {
            throw new TypeError('WizardPage: languageService.getLanguage() must return a non-empty string');
        }
        const currentLanguage = currentLanguageValue.trim();
        const languageCandidates = this.#dependencies.languageService.getAvailableLanguages();
        return {
            getIconSync: (name, options) =>
                this.#dependencies.getIconSync(name, {
                    width: options.width,
                    height: options.height
                }),
            sanitizer: this.#dependencies.sanitizer,
            state: this.#dependencies.state,
            currentLanguage,
            languageOptions: buildLanguageOptions(languageCandidates, currentLanguage)
        };
    }

    updateProgress(ui: WizardUi): void {
        const current = this.#dependencies.state.stepIndex + 1;
        const total = this.#dependencies.state.totalSteps;
        const ratio = total > 0 ? current / total : 0;
        const percent = normalizeProgressRatio(ratio) ?? 0;
        syncDeterminateProgress({
            fillElement: ui.progressFill,
            progress: percent,
            setStyle: (element, property, value): void => {
                if (!(element instanceof HTMLElement)) {
                    throw new TypeError('Wizard progress fill must be an HTMLElement');
                }
                this.#dependencies.updateStyle(element, property, value);
            }
        });
        this.#dependencies.updateText(ui.progressText, i18n.t('wizard.progress.stepOf', { current, total }));
    }

    syncNavigation(ui: WizardUi, stepId: WizardStepId): void {
        const isBusy = this.#dependencies.state.isBusy;
        const showBack = stepId !== 'welcome' && stepId !== 'complete';
        const canGoBack = showBack && !isBusy;

        this.#dependencies.toggleHidden(ui.navBackButton, !showBack);
        this.#dependencies.updateProperty(ui.navBackButton, 'disabled', !canGoBack);
        ui.navBackButton.toggleAttribute('aria-disabled', !canGoBack);
        const backLabel = i18n.t('wizard.navigation.back');
        this.#dependencies.updateText(ui.navBackButton, backLabel);
        syncAttributeValue(ui.navBackButton, 'aria-label', backLabel);
        if (getTooltipText(ui.navBackButton) !== backLabel) setTooltipText(ui.navBackButton, backLabel);

        ui.navNextButton.toggleAttribute('data-licensing-mutation', stepId === 'product_access');
        const isAccountSubmitBlocked = stepId === 'account' && !this.#isAccountSubmitEligible();
        const declarationBlocked = stepId === 'use' && (this.#dependencies.state.declarationSelection === null || (this.#dependencies.state.declarationSelection === 'personal' && !this.#dependencies.state.attestationConfirmed));
        const selectedProductAccess = stepId === 'product_access' ? this.selectedProductAccessFlow(ui) : null;
        if (stepId === 'product_access') this.#prefillOrganizationCountry(ui, selectedProductAccess);
        const productAccess = stepId === 'product_access' ? this.#productAccessNavigation(ui, isBusy, selectedProductAccess) : null;
        this.#dependencies.toggleHidden(ui.navNextButton, stepId === 'product_access' && selectedProductAccess === null);
        const isNextDisabled = isBusy || isAccountSubmitBlocked || declarationBlocked || productAccess?.disabled === true;
        this.#dependencies.updateProperty(ui.navNextButton, 'disabled', isNextDisabled);
        ui.navNextButton.toggleAttribute('aria-disabled', isNextDisabled);

        const label = productAccess?.label ?? this.#getNextLabel(stepId);
        syncAttributeValue(ui.navNextButton, 'data-action', productAccess?.action ?? 'wizard-next');
        this.#dependencies.updateText(ui.navNextButton, label);
        syncAttributeValue(ui.navNextButton, 'aria-label', label);
        if (getTooltipText(ui.navNextButton) !== label) setTooltipText(ui.navNextButton, label);
    }

    syncUseSelection(ui: WizardUi): void {
        const selected = this.#dependencies.state.declarationSelection;
        const personalInput = narrowInput(this.#dependencies.requireHTMLElement('input[name="wizard-use"][value="personal"]', ui.content), 'Personal use choice');
        const organizationInput = narrowInput(this.#dependencies.requireHTMLElement('input[name="wizard-use"][value="organization_commercial"]', ui.content), 'Organization use choice');
        const personalCard = personalInput.closest('.wizard-choice-card');
        const organizationCard = organizationInput.closest('.wizard-choice-card');
        if (!(personalCard instanceof HTMLElement) || !(organizationCard instanceof HTMLElement)) throw new TypeError('Wizard use choice cards are unavailable');
        const attestationRegion = this.#dependencies.requireHTMLElement('.wizard-attestation-region', ui.content);
        const attestationInput = narrowInput(this.#dependencies.requireHTMLElement('#wizard-personal-attestation', attestationRegion), 'Personal use attestation');
        const personalSelected = selected === 'personal';

        this.#dependencies.updateProperty(personalInput, 'checked', selected === 'personal');
        this.#dependencies.updateProperty(organizationInput, 'checked', selected === 'organization_commercial');
        this.#dependencies.toggleClassName(personalCard, 'is-selected', selected === 'personal');
        this.#dependencies.toggleClassName(organizationCard, 'is-selected', selected === 'organization_commercial');
        this.#dependencies.toggleClassName(attestationRegion, 'is-expanded', personalSelected);
        this.#dependencies.updateAttribute(attestationRegion, 'aria-hidden', personalSelected ? 'false' : 'true');
        this.#dependencies.updateAttribute(attestationRegion, 'inert', personalSelected ? null : '');
        this.#dependencies.updateProperty(attestationInput, 'checked', this.#dependencies.state.attestationConfirmed);
        this.#dependencies.updateProperty(attestationInput, 'disabled', !personalSelected);
    }

    selectedProductAccessFlow(ui: WizardUi): ProductAccessFlow | null {
        const selected = optionalInput(dom.resolve('input[name="wizard-product-access"]:checked', ui.content), 'Selected product access choice');
        return selected === null ? null : productAccessFlow(selected.value);
    }

    syncProductAccessSelection(ui: WizardUi, selected: ProductAccessFlow | null, focusPanel: boolean): void {
        for (const element of dom.resolveAll('input[name="wizard-product-access"]', ui.content)) {
            if (!(element instanceof HTMLInputElement)) throw new TypeError('Wizard product access choice must be an input');
            const flow = productAccessFlow(element.value);
            if (flow === null) throw new TypeError('Wizard product access choice is invalid');
            const card = element.closest('.wizard-choice-card');
            if (!(card instanceof HTMLElement)) throw new TypeError('Wizard product access choice card is unavailable');
            this.#dependencies.updateProperty(element, 'checked', flow === selected);
            this.#dependencies.toggleClassName(card, 'is-selected', flow === selected);
        }
        let activePanel: HTMLElement | null = null;
        for (const element of dom.resolveAll('[data-product-access-panel]', ui.content)) {
            if (!(element instanceof HTMLElement)) throw new TypeError('Wizard product access panel must be an element');
            const active = element.dataset['productAccessPanel'] === selected;
            this.#dependencies.toggleHidden(element, !active);
            if (active) activePanel = element;
        }
        const prompt = this.#dependencies.requireHTMLElement('[data-wizard-path-prompt]', ui.content);
        this.#dependencies.toggleHidden(prompt, selected !== null);
        this.#prefillOrganizationCountry(ui, selected);
        this.syncNavigation(ui, 'product_access');
        if (focusPanel && activePanel !== null) {
            activePanel.focus({ preventScroll: true });
            scrollElementIntoView(activePanel);
        }
    }

    #productAccessNavigation(ui: WizardUi, isBusy: boolean, selected: ProductAccessFlow | null): ProductAccessNavigation {
        const operation = this.#dependencies.state.status?.operation ?? null;
        const operationInProgress = operation !== null && isLicensingOperationInProgress(operation.state);
        let navigation: ProductAccessNavigation;
        if (selected === null) {
            navigation = { action: 'wizard-next', disabled: true, label: i18n.t('wizard.productAccess.blocked.choosePath'), reason: i18n.t('wizard.productAccess.blocked.choosePath') };
        } else if (selected === 'evaluation') {
            navigation = this.#evaluationNavigation(ui);
        } else if (selected === 'online_activation') {
            navigation = this.#activationNavigation(ui);
        } else {
            navigation = { action: 'wizard-export-offline', disabled: false, label: i18n.t('wizard.productAccess.offline.export'), reason: '' };
        }
        const authoritativeFlow = this.#dependencies.state.status?.selectedProductAccessFlow ?? null;
        if (isBusy || (operationInProgress && selected === authoritativeFlow)) navigation = { ...navigation, disabled: true, reason: i18n.t('wizard.productAccess.blocked.operationInProgress') };
        this.#syncProductAccessReason(ui, selected, navigation.reason);
        return navigation;
    }

    #evaluationNavigation(ui: WizardUi): ProductAccessNavigation {
        if (this.#dependencies.state.status?.pendingEvaluation !== null) return { action: 'wizard-activate-evaluation', disabled: false, label: i18n.t('wizard.productAccess.evaluation.activate'), reason: '' };
        const form = dom.resolve('#wizard-organization-form', ui.content);
        if (!(form instanceof HTMLFormElement)) return { action: 'wizard-start-evaluation', disabled: true, label: i18n.t('wizard.productAccess.evaluation.action'), reason: i18n.t('wizard.productAccess.blocked.organizationFields') };
        for (const control of Array.from(form.elements)) {
            if (control instanceof HTMLInputElement && control.type !== 'checkbox' && (control.value.trim().length === 0 || !control.checkValidity())) return { action: 'wizard-start-evaluation', disabled: true, label: i18n.t('wizard.productAccess.evaluation.action'), reason: i18n.t('wizard.productAccess.blocked.organizationFields') };
        }
        const acceptance = optionalInput(dom.resolve('#wizard-evaluation-acknowledgement', ui.content), 'Wizard evaluation acceptance');
        if (acceptance?.checked !== true) return { action: 'wizard-start-evaluation', disabled: true, label: i18n.t('wizard.productAccess.evaluation.action'), reason: i18n.t('wizard.productAccess.blocked.evaluationAcceptance') };
        return { action: 'wizard-start-evaluation', disabled: false, label: i18n.t('wizard.productAccess.evaluation.action'), reason: '' };
    }

    #activationNavigation(ui: WizardUi): ProductAccessNavigation {
        const key = optionalInput(dom.resolve('#wizard-product-key', ui.content), 'Wizard product key input');
        if ((key?.value.trim().length ?? 0) < 16) return { action: 'wizard-activate', disabled: true, label: i18n.t('wizard.productAccess.key.action'), reason: i18n.t('wizard.productAccess.blocked.licenseKey') };
        const acceptance = optionalInput(dom.resolve('#wizard-activation-acceptance', ui.content), 'Wizard activation acceptance');
        if (acceptance?.checked !== true) return { action: 'wizard-activate', disabled: true, label: i18n.t('wizard.productAccess.key.action'), reason: '' };
        return { action: 'wizard-activate', disabled: false, label: i18n.t('wizard.productAccess.key.action'), reason: '' };
    }

    #prefillOrganizationCountry(ui: WizardUi, selected: ProductAccessFlow | null): void {
        if (selected !== 'evaluation') return;
        const input = optionalInput(dom.resolve('#wizard-organization-country', ui.content), 'Wizard organization country input');
        if (input === null || input.value.length !== 0) return;
        const countryCode = resolveBrowserCountryCode();
        if (countryCode !== null) input.value = countryCode;
    }

    #syncProductAccessReason(ui: WizardUi, selected: ProductAccessFlow | null, message: string): void {
        for (const element of dom.resolveAll('[data-wizard-action-reason]', ui.content)) {
            if (!(element instanceof HTMLElement)) throw new TypeError('Wizard product access reason must be an element');
            const active = selected !== null && element.closest(`[data-product-access-panel="${selected}"]`) !== null;
            this.#dependencies.updateText(element, active ? message : '');
            this.#dependencies.toggleHidden(element, !active || message.length === 0);
        }
        if (message.length === 0) ui.navNextButton.removeAttribute('aria-describedby');
        else this.#dependencies.updateAttribute(ui.navNextButton, 'aria-describedby', selected === null ? 'wizard-path-prompt' : `wizard-${selected}-action-reason`);
    }

    #isAccountSubmitEligible(): boolean {
        const { form } = this.requireAccountUi();
        return isWizardAccountFormEligibleForSubmit(form);
    }

    #getNextLabel(stepId: WizardStepId): string {
        switch (stepId) {
            case 'welcome':
                return i18n.t('wizard.navigation.getStarted');
            case 'license':
                return i18n.t('wizard.navigation.acceptLicense');
            case 'use':
                return i18n.t('wizard.navigation.continue');
            case 'product_access':
                return i18n.t('wizard.navigation.continue');
            case 'account':
                return i18n.t('wizard.navigation.createAccount');
            case 'complete':
                return this.#dependencies.state.isSessionActivationRequired ? i18n.t('wizard.navigation.signIn') : i18n.t('wizard.navigation.enterSoai');
        }
    }
}

export { WizardPageUiController };
