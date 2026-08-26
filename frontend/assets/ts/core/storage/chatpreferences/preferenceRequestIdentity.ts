/* SoAI - Preference request identity admission [frontend/assets/ts/core/storage/chatpreferences/preferenceRequestIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageRuntimeState } from '@core/storage/service/types.ts';

type PreferenceRequestIdentity = Readonly<{ userId: string; windowId: string }>;

const readPreferenceRequestIdentity = (state: StorageRuntimeState): PreferenceRequestIdentity | null => {
    const userId = state.session['userId'];
    const windowId = state.windowIdentity;
    return typeof userId === 'string' && userId.trim() && windowId ? { userId: userId.trim(), windowId } : null;
};

const requirePreferenceRequestIdentity = (state: StorageRuntimeState): PreferenceRequestIdentity => {
    const identity = readPreferenceRequestIdentity(state);
    if (!identity) throw new Error('Chat preference admission requires authenticated user and window identities.');
    return identity;
};

const preferenceRequestIdentityIsCurrent = (state: StorageRuntimeState, captured: PreferenceRequestIdentity): boolean => {
    const current = readPreferenceRequestIdentity(state);
    return state.isAuthenticated && current?.userId === captured.userId && current.windowId === captured.windowId;
};

const preferenceRequestIdentityMatches = (state: StorageRuntimeState, active: PreferenceRequestIdentity | null, captured: PreferenceRequestIdentity): boolean => {
    const current = readPreferenceRequestIdentity(state);
    return state.isAuthenticated && current?.userId === captured.userId && current.windowId === captured.windowId && active?.userId === captured.userId && active.windowId === captured.windowId;
};

export { preferenceRequestIdentityIsCurrent, preferenceRequestIdentityMatches, readPreferenceRequestIdentity, requirePreferenceRequestIdentity };
export type { PreferenceRequestIdentity };
