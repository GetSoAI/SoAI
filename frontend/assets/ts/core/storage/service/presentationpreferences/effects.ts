/* SoAI - Shared storage presentation preferences effects [frontend/assets/ts/core/storage/service/presentationpreferences/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { PERSIST_GROUPS } from '@core/storage/service/presentationpreferences/constants.ts';
import { applyPresentationPreferenceState } from '@core/storage/service/presentationpreferences/apply.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

const createPresentationPreferenceEffects = (core: StorageRuntime): { clearAll: () => void } => {
    const state = core.state;

    const clearAll = (): void => {
        const theme = state.cache.ui.theme;
        state.cache = core.createDefaults();
        state.cache.ui.theme = theme;
        core.syncLocal('ui');
        core.writeStorage('localStorage', state.localKeys.chat, null);
        applyPresentationPreferenceState(core);
        if (state.isAuthenticated) {
            for (const group of PERSIST_GROUPS) {
                terminateHandledPromise(core.queuePersist(group));
            }
        }
        core.scheduleBroadcast();
    };

    return {
        clearAll
    };
};

export { createPresentationPreferenceEffects };
