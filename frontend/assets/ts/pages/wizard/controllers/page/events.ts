/* SoAI - Wizard page controller events [frontend/assets/ts/pages/wizard/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WizardMotionController } from '@pages/wizard/controllers/WizardMotionController.ts';
import { bindFormSubmit } from '@core/dom/formSubmit.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { syncFlagSelect } from '@core/ui/dropdown/flagSelect.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { WizardState } from '@features/wizard/public.ts';
import { AI_PROVIDER_FORM_ID } from '@pages/wizard/rendering/aisetup/connect/view.ts';
import { AI_SEARCH_FORM_ID } from '@pages/wizard/rendering/aisetup/models/view.ts';
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
    handleLanguageError: (error: Error) => void;
}

const wireWizardRootEvents = (host: WizardRootEventHost): void => {
    new WizardMotionController(host.root, host.signal);
    const languageRequests = new LatestRequestController();
    const cancelLanguageRequests = (): void => languageRequests.invalidate();
    host.signal.addEventListener('abort', cancelLanguageRequests, { once: true });
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
    for (const formId of [AI_PROVIDER_FORM_ID, AI_SEARCH_FORM_ID]) {
        bindFormSubmit({
            root: host.root,
            signal: host.signal,
            formId,
            capture: true,
            preventDefault: true,
            onSubmit: ({ form }): void => host.service.handleAiSetupSubmit(form)
        });
    }
    const handleInput = (event: Event): void => {
        const target = event.target;
        if (target instanceof HTMLInputElement && (target.name === 'wizard-product-access' || target.id === 'wizard-offline-certificate')) return;
        host.service.handleInput(target);
    };
    host.root.addEventListener('input', handleInput, { signal: host.signal, capture: true });
    const handleChange = (event: Event): void => handleWizardRootChange(host, event, languageRequests);
    host.root.addEventListener('change', handleChange, { signal: host.signal, capture: true });
};

const handleWizardRootSubmit = (host: WizardRootEventHost): void => {
    void host.service.handleNext().catch((error) => {
        host.logError('form submit failed', ensureError(error));
    });
};

const handleWizardRootChange = (host: WizardRootEventHost, event: Event, languageRequests: LatestRequestController): void => {
    const target = event.target;
    if (target instanceof HTMLInputElement && (target.name === 'wizard-product-access' || target.id === 'wizard-offline-certificate')) {
        host.service.handleInput(target);
        return;
    }
    if (!(target instanceof HTMLSelectElement) || target.id !== 'language-select') {
        return;
    }
    syncFlagSelect(target);

    const stepId = host.state.steps[host.state.stepIndex];
    if (stepId !== 'welcome') {
        return;
    }

    const nextLanguage = readTrimmedSelectValue(target);
    if (!nextLanguage) {
        return;
    }

    void languageRequests
        .runLatest(async (request) => {
            try {
                await host.languageService.setLanguage(nextLanguage);
            } catch (error) {
                if (!request.isCurrent()) return;
                if (target.isConnected) {
                    target.value = host.languageService.getLanguage();
                    syncFlagSelect(target);
                }
                throw error;
            }
        })
        .catch((error) => host.handleLanguageError(ensureError(error)));
};

export { wireWizardRootEvents };
export type { WizardLanguageHost, WizardRootEventHost };
