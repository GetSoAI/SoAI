/* SoAI - Irreversible wizard completion reconciliation [frontend/assets/ts/core/auth/wizardCompletion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUTH_TAG } from '@core/auth/constants.ts';
import type { AuthManagerServiceResolver, AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import { activateIssuedSession } from '@core/auth/loginEffects.ts';
import { isSessionInvalidApiError } from '@core/auth/sessionFailure.ts';
import type { LoginResult, WebuiUser, WizardCompletionResult } from '@core/auth/types.ts';
import { isDetailedWizardStatus, type WizardCompletedSummary } from '@core/api/contracts/wizardLicensingContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';

type LoginOperation = (state: AuthManagerStateHandle, username: string, password: string, resolveApi: AuthManagerServiceResolver['resolveApi'], resolveStorage: AuthManagerServiceResolver['resolveStorage'], expectedEpoch: number) => Promise<LoginResult>;

const pendingResult = (): WizardCompletionResult => ({
    status: 'reconciliationPending',
    error: i18n.t('wizard.userCreation.errors.reconciliationPending')
});

const activationFailureResult = (user: WebuiUser | null, completion: WizardCompletedSummary): WizardCompletionResult => ({
    status: 'sessionActivationFailed',
    user,
    completion,
    error: i18n.t('wizard.userCreation.errors.loginAfterSetupFailed')
});

const reconcileWizardCompletion = async (state: AuthManagerStateHandle, username: string, password: string, language: string, resolveApi: AuthManagerServiceResolver['resolveApi'], resolveStorage: AuthManagerServiceResolver['resolveStorage'], login: LoginOperation, expectedEpoch: number = state.authEpoch): Promise<WizardCompletionResult> => {
    if (!username || !password) {
        return { status: 'rejected', error: i18n.t('wizard.userCreation.errors.credentialsRequired') };
    }

    const storage = await resolveStorage();
    const api = await resolveApi();
    const wasPending = storage.isWizardCompletionPending();
    let committedInRequest = false;
    let committedUser: WebuiUser | null = null;
    let completionSummary: WizardCompletedSummary | null = null;
    let wizardStatus;

    try {
        const lookup = await api.webui.wizard.status({ authTransitionOwned: true });
        if (!isDetailedWizardStatus(lookup)) {
            throw new Error('Wizard status details are unavailable');
        }
        wizardStatus = lookup;
        state.wizardStatusSnapshot = lookup;
        completionSummary = lookup.completedSummary;
    } catch (error) {
        errorHandler.warn(AUTH_TAG, 'Wizard completion status lookup failed', ensureError(error));
        return wasPending ? pendingResult() : { status: 'rejected', error: i18n.t('wizard.userCreation.errors.generic') };
    }

    if (wizardStatus.setupNeeded) {
        storage.setWizardCompletionPending(true);
        try {
            const completion = await api.webui.wizard.complete(wizardStatus.draftRevision, username, password, language, { authTransitionOwned: true });
            committedInRequest = true;
            committedUser = completion.user;
            completionSummary = completion.completion;
            state.wizardStatusSnapshot = null;
        } catch (error) {
            const completionError = ensureError(error);
            try {
                const lookup = await api.webui.wizard.status({ authTransitionOwned: true });
                if (!isDetailedWizardStatus(lookup)) {
                    throw new Error('Wizard reconciliation details are unavailable');
                }
                state.wizardStatusSnapshot = lookup;
                completionSummary = lookup.completedSummary;
                if (lookup.setupNeeded) {
                    storage.setWizardCompletionPending(false);
                    errorHandler.warn(AUTH_TAG, 'Wizard completion request failed before commit', completionError);
                    return { status: 'rejected', error: i18n.t('wizard.userCreation.errors.generic') };
                }
            } catch (reconciliationError) {
                errorHandler.error(AUTH_TAG, 'Wizard completion outcome could not be reconciled', new AggregateError([completionError, ensureError(reconciliationError)], 'Wizard completion and reconciliation failed'));
                return pendingResult();
            }
        }
    }

    if (completionSummary === null) {
        errorHandler.warn(AUTH_TAG, 'Completed wizard status omitted its completion summary', new Error('Wizard completion summary is unavailable'));
        return pendingResult();
    }

    try {
        const activeUser = await activateIssuedSession(state, resolveApi, resolveStorage, expectedEpoch);
        return { status: 'authenticated', user: activeUser, completion: completionSummary };
    } catch (error) {
        const activationError = ensureError(error);
        if (!isSessionInvalidApiError(activationError)) {
            errorHandler.warn(AUTH_TAG, 'Wizard session activation outcome is unresolved', activationError);
            return pendingResult();
        }
        if (committedInRequest) {
            errorHandler.warn(AUTH_TAG, 'Wizard completion response did not establish its session', activationError);
            return activationFailureResult(committedUser, completionSummary);
        }
    }

    try {
        const loginResult = await login(state, username, password, resolveApi, resolveStorage, expectedEpoch);
        if (loginResult.status === 'authenticated') {
            return { status: 'authenticated', user: loginResult.user, completion: completionSummary };
        }
        return activationFailureResult(committedUser, completionSummary);
    } catch (error) {
        errorHandler.warn(AUTH_TAG, 'Recovered wizard completion login outcome is unresolved', ensureError(error));
        return pendingResult();
    }
};

export { reconcileWizardCompletion };
export type { LoginOperation };
