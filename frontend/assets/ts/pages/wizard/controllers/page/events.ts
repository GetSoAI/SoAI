/* SoAI - Wizard page controller events [frontend/assets/ts/pages/wizard/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindFormSubmit } from '@core/dom/formSubmit.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { WizardState } from '@features/wizard/public.ts';
import { WizardPageService } from '@pages/wizard/services/service.ts';

interface WizardLanguageHost {
    getLanguage(): string;
    setLanguage(language: string): Promise<void>;
}

interface WizardRootEventHost {
    root: HTMLElement;
    signal: AbortSignal;
    service: WizardPageService;
    state: WizardState;
    languageService: WizardLanguageHost;
    logError: (operation: string, error: Error) => void;
}

const wireWizardRootEvents = (host: WizardRootEventHost): void => {
    bindFormSubmit({
        root: host.root,
        signal: host.signal,
        formId: 'admin-user-form',
        capture: true,
        preventDefault: true,
        onSubmit: (): void => {
            handleWizardRootSubmit(host);
        }
    });
    const handleInput = (event: Event): void => {
        const target = event.target;
        if (target instanceof HTMLInputElement && (target.name === 'wizard-product-access' || target.id === 'wizard-offline-certificate')) return;
        host.service.handleInput(target);
    };
    host.root.addEventListener('input', handleInput, { signal: host.signal, capture: true });
    const handleChange = (event: Event): void => handleWizardRootChange(host, event);
    host.root.addEventListener('change', handleChange, { signal: host.signal, capture: true });
};

const handleWizardRootSubmit = (host: WizardRootEventHost): void => {
    void host.service.handleNext().catch((error) => {
        host.logError('form submit failed', ensureError(error));
    });
};

const handleWizardRootChange = (host: WizardRootEventHost, event: Event): void => {
    const target = event.target;
    if (target instanceof HTMLInputElement && (target.name === 'wizard-product-access' || target.id === 'wizard-offline-certificate')) {
        host.service.handleInput(target);
        return;
    }
    if (!(target instanceof HTMLSelectElement) || target.id !== 'language-select') {
        return;
    }

    const stepId = host.state.steps[host.state.stepIndex];
    if (stepId !== 'welcome') {
        return;
    }

    const nextLanguage = readTrimmedSelectValue(target);
    if (!nextLanguage) {
        return;
    }

    const current = host.languageService.getLanguage();
    if (nextLanguage === current) {
        return;
    }

    void host.languageService.setLanguage(nextLanguage).catch((error) => {
        host.logError('language update failed', ensureError(error));
    });
};

export { wireWizardRootEvents };
export type { WizardLanguageHost, WizardRootEventHost };
