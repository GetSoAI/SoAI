/* SoAI - Preference request identity admission [frontend/assets/ts/core/storage/chatpreferences/preferenceRequestIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageRuntimeState, PreferenceRequestIdentity } from '@core/storage/service/types.ts';

const readPreferenceRequestIdentity = (state: StorageRuntimeState): PreferenceRequestIdentity | null => {
    const userId = state.session['userId'];
    const windowId = state.windowIdentity;
    const authEpoch = state.readAuthEpoch();
    if (!Number.isSafeInteger(authEpoch) || authEpoch < 0) throw new Error('Preference admission requires a valid authentication epoch.');
    return typeof userId === 'string' && userId.trim() && windowId ? Object.freeze({ userId: userId.trim(), windowId, authEpoch }) : null;
};

const requirePreferenceRequestIdentity = (state: StorageRuntimeState): PreferenceRequestIdentity => {
    const identity = readPreferenceRequestIdentity(state);
    if (!identity) throw new Error('Chat preference admission requires authenticated user and window identities.');
    return identity;
};

const preferenceRequestIdentityMatchesSession = (state: StorageRuntimeState, captured: PreferenceRequestIdentity): boolean => {
    const current = readPreferenceRequestIdentity(state);
    return current?.userId === captured.userId && current.windowId === captured.windowId && current.authEpoch === captured.authEpoch;
};

const preferenceRequestIdentityIsCurrent = (state: StorageRuntimeState, captured: PreferenceRequestIdentity): boolean => state.isAuthenticated && preferenceRequestIdentityMatchesSession(state, captured);

const preferenceRequestIdentityMatches = (state: StorageRuntimeState, active: PreferenceRequestIdentity | null, captured: PreferenceRequestIdentity): boolean => {
    return preferenceRequestIdentityIsCurrent(state, captured) && active?.userId === captured.userId && active.windowId === captured.windowId && active.authEpoch === captured.authEpoch;
};

export { preferenceRequestIdentityIsCurrent, preferenceRequestIdentityMatchesSession, preferenceRequestIdentityMatches, readPreferenceRequestIdentity, requirePreferenceRequestIdentity };
export type { PreferenceRequestIdentity };
