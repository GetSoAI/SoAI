/* SoAI - Authentication epoch admission and synchronous intent delivery [frontend/assets/ts/core/auth/epochIntent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { AUTH_TAG } from '@core/auth/constants.ts';
import type { AuthEpochIntent } from '@core/auth/types.ts';
import type { AuthManagerStateHandle } from '@core/auth/internalContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

const notifyEpochIntent = (state: AuthManagerStateHandle, type: AuthEpochIntent['type']): number => {
    const intent: AuthEpochIntent = Object.freeze({ type, authEpoch: state.authEpoch });
    for (const callback of [...state.epochIntentCallbacks]) {
        if (state.authEpoch !== intent.authEpoch) break;
        if (!state.epochIntentCallbacks.includes(callback)) continue;
        try {
            callback(intent);
        } catch (error) {
            errorHandler.error(AUTH_TAG, 'Authentication intent observer failed', ensureError(error));
        }
    }
    return intent.authEpoch;
};

const beginAuthenticatedEpoch = (state: AuthManagerStateHandle): number => {
    state.authEpoch += 1;
    state.terminalEpoch = null;
    return notifyEpochIntent(state, 'authenticated');
};

const beginTerminalAuthIntent = (state: AuthManagerStateHandle): number => {
    state.authEpoch += 1;
    state.terminalEpoch = state.authEpoch;
    state.isLoggingOut = true;
    return notifyEpochIntent(state, 'terminal');
};

const canApplyAuthenticatedEpoch = (state: AuthManagerStateHandle, epoch: number): boolean => state.authEpoch === epoch && state.terminalEpoch === null;

export { beginAuthenticatedEpoch, beginTerminalAuthIntent, canApplyAuthenticatedEpoch };
