/* SoAI - Shared storage presentation preferences service [frontend/assets/ts/core/storage/service/presentationpreferences/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createPresentationPreferenceActions } from '@core/storage/service/presentationpreferences/actions.ts';
import { createPresentationClockPreferenceMethods } from '@core/storage/service/presentationpreferences/clock.ts';
import { createPresentationPreferenceEffects } from '@core/storage/service/presentationpreferences/effects.ts';
import { createPresentationPreferenceState } from '@core/storage/service/presentationpreferences/state.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

type PresentationPreferenceMethods = ReturnType<typeof createPresentationPreferenceState> & ReturnType<typeof createPresentationPreferenceActions> & ReturnType<typeof createPresentationClockPreferenceMethods> & ReturnType<typeof createPresentationPreferenceEffects>;

const createPresentationPreferenceMethods = (core: StorageRuntime): PresentationPreferenceMethods => {
    const state = createPresentationPreferenceState(core);
    const actions = createPresentationPreferenceActions(core);
    const clock = createPresentationClockPreferenceMethods(core);
    const effects = createPresentationPreferenceEffects(core);
    return {
        ...state,
        ...actions,
        ...clock,
        ...effects
    };
};

export { createPresentationPreferenceMethods };
