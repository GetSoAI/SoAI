/* SoAI - Wizard page effects [frontend/assets/ts/pages/wizard/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setFirstRunModalsPending } from '@core/firstrun/state.ts';
import type { WizardCompletionResult, WizardStatus } from '@core/auth/public.ts';
import { isWizardSetupCompleteStatus } from '@core/auth/wizardStatus.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { WizardPageEffectsHost } from '@pages/wizard/controllers/page/types.ts';

const ensureWizardStatusSnapshot = async (host: WizardPageEffectsHost, options: { force?: boolean } = {}): Promise<WizardStatus | null> => {
    if (!options.force) {
        const status = host.getWizardStatus();
        if (status) {
            return status;
        }
    }

    const auth = host.getAuth();
    if (!auth) {
        host.logWarn('Auth service is unavailable while resolving wizard status');
        return null;
    }

    if (!options.force) {
        const cached = auth.getWizardStatusSnapshot?.();
        if (cached) {
            host.setWizardStatus(cached);
            return cached;
        }
    }

    if (isFunction(auth.checkWizardStatus)) {
        try {
            await auth.checkWizardStatus();
        } catch (error) {
            const runtimeError = ensureError(error);
            host.logWarn('Wizard status lookup failed', runtimeError);
        }
    }

    const resolvedStatus = auth.getWizardStatusSnapshot?.() || null;
    host.setWizardStatus(resolvedStatus);
    return resolvedStatus;
};

const markWizardHasUsers = (host: WizardPageEffectsHost): void => {
    host.setWizardStatus(null);
};

const persistWizardState = async (host: WizardPageEffectsHost): Promise<void> => {
    const storage = host.getStorage();
    if (!storage || !isFunction(storage.setWizardCompleted)) {
        return;
    }
    try {
        await storage.setWizardCompleted();
    } catch (error) {
        const runtimeError = ensureError(error);
        host.logWarn('Failed to persist wizard state', runtimeError);
    }
};

const markWizardFirstRunModalsPending = async (host: WizardPageEffectsHost): Promise<void> => {
    const storage = host.getStorage();
    if (!storage || !isFunction(storage.get) || !isFunction(storage.set)) {
        return;
    }
    const readStorage = storage.get;
    const writeStorage = storage.set;
    try {
        const firstRunStorage: FirstRunStateStorage = {
            get: (key, defaultValue) => readStorage(key, defaultValue),
            set: (key, value) => writeStorage(key, value)
        };
        setFirstRunModalsPending(firstRunStorage, ['dashboardIntro', 'pluginsIntro']);
    } catch (error) {
        const runtimeError = ensureError(error);
        host.logWarn('Failed to persist wizard first-run modal state', runtimeError);
    }
};

const shouldShowWizard = async (host: WizardPageEffectsHost): Promise<boolean> => {
    const visible = host.getWizardVisible();
    if (visible !== null) {
        return visible;
    }

    const storage = host.getStorage();
    const wizardCompletionPending = storage && isFunction(storage.isWizardCompletionPending) ? storage.isWizardCompletionPending() : false;
    if (wizardCompletionPending && host.isAuthenticated()) {
        host.setWizardVisible(true);
        return true;
    }

    const snapshot = await ensureWizardStatusSnapshot(host);
    if (isWizardSetupCompleteStatus(snapshot)) {
        host.setWizardVisible(false);
        return false;
    }

    host.setWizardVisible(true);
    return true;
};

const shouldResumeAtCompletionStep = (host: WizardPageEffectsHost): boolean => {
    const storage = host.getStorage();
    if (!storage || !isFunction(storage.isWizardCompletionPending) || !storage.isWizardCompletionPending()) {
        return false;
    }
    const status = host.getWizardStatus();
    return isWizardSetupCompleteStatus(status);
};

const submitWizardAccount = async (host: WizardPageEffectsHost, username: string, password: string): Promise<WizardCompletionResult> => {
    const auth = host.getAuth();
    if (!auth || !isFunction(auth.completeWizard)) {
        throw new Error('WizardPage requires auth.completeWizard for account setup');
    }
    return auth.completeWizard(username, password);
};

export { ensureWizardStatusSnapshot, markWizardFirstRunModalsPending, markWizardHasUsers, persistWizardState, shouldResumeAtCompletionStep, shouldShowWizard, submitWizardAccount };
