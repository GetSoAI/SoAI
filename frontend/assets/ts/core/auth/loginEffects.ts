/* SoAI - Authenticated session establishment outcomes [frontend/assets/ts/core/auth/loginEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readApiRetryAfterSeconds } from '@core/api/errorPayloads.ts';
import { APIError } from '@core/apiError.ts';
import { AUTH_TAG } from '@core/auth/constants.ts';
import type { AuthManagerServiceResolver, AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import type { LoginResult, WebuiUser } from '@core/auth/types.ts';
import { applyUserSession } from '@core/auth/state.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';

const resolveRejectedLogin = (error: Error): LoginResult => {
    if (!(error instanceof APIError)) {
        errorHandler.error(AUTH_TAG, 'Login request failed', error);
        throw error;
    }
    if (error.status === 401) {
        return { status: 'rejected', error: i18n.t('login.errors.invalidCredentials') };
    }
    if (error.status === 429) {
        const retryAfterSecondsValue = readApiRetryAfterSeconds(error);
        const retryAfterSeconds = retryAfterSecondsValue === null ? null : Math.max(1, Math.ceil(retryAfterSecondsValue));
        if (retryAfterSeconds !== null) {
            return {
                status: 'rejected',
                error: i18n.t('login.errors.rateLimitedCountdown', { seconds: retryAfterSeconds }),
                retryAfterSeconds
            };
        }
    }
    errorHandler.warn(AUTH_TAG, 'Login request rejected', error);
    return { status: 'rejected', error: i18n.t('login.errors.loginFailed') };
};

const activateIssuedSession = async (state: AuthManagerStateHandle, resolveApi: AuthManagerServiceResolver['resolveApi'], resolveStorage: AuthManagerServiceResolver['resolveStorage'], expectedEpoch: number): Promise<WebuiUser> => {
    const api = await resolveApi();
    const user = await api.webui.auth.getMe({ authTransitionOwned: true });
    const wasApplied = await applyUserSession(state, user, resolveStorage, undefined, expectedEpoch);
    if (!wasApplied) {
        throw new Error('Authenticated session response did not contain a valid user');
    }
    return user;
};

const loginAuthManager = async (state: AuthManagerStateHandle, username: string, password: string, resolveApi: AuthManagerServiceResolver['resolveApi'], resolveStorage: AuthManagerServiceResolver['resolveStorage'], expectedEpoch: number = state.authEpoch): Promise<LoginResult> => {
    const api = await resolveApi();
    try {
        await api.webui.auth.login(username, password);
    } catch (error) {
        return resolveRejectedLogin(ensureError(error));
    }

    try {
        const activeUser = await activateIssuedSession(state, resolveApi, resolveStorage, expectedEpoch);
        return { status: 'authenticated', user: activeUser };
    } catch (error) {
        errorHandler.warn(AUTH_TAG, 'Login succeeded but session activation failed', ensureError(error));
        return { status: 'sessionActivationFailed', error: i18n.t('login.errors.sessionActivationFailed') };
    }
};

export { activateIssuedSession, loginAuthManager };
