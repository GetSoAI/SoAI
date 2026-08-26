/* SoAI - Shared storage apply [frontend/assets/ts/core/storage/service/presentationpreferences/apply.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyPresentationPreferenceDomEffects } from '@core/storage/service/presentationpreferences/domEffects.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

const applyPresentationPreferenceState = (core: StorageRuntime): void => {
    applyPresentationPreferenceDomEffects({
        preferences: core.state.cache.ui,
        includeHeaderAutoHideClass: false,
        dispatchClockChanged: true,
        applyTheme: core.applyTheme,
        effects: {
            bodyClass: core.bodyClass,
            setGlassDisabled: core.setGlassDisabled,
            setAttr: core.setAttr
        }
    });
};

export { applyPresentationPreferenceState };
