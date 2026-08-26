/* SoAI - Shared storage clock preferences [frontend/assets/ts/core/storage/clockPreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import type { UiPreferences } from '@core/storage/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface ClockPreferenceState {
    headerClockEnabled: boolean;
    clockSecondsEnabled: boolean;
}

const CLOCK_PREFERENCES_CHANGED_EVENT = 'soai:clockpreferences:changed';

const normalizeClockPreferenceState = (state: ClockPreferenceState): ClockPreferenceState => {
    const headerClockEnabled = state.headerClockEnabled !== false;
    return {
        headerClockEnabled,
        clockSecondsEnabled: headerClockEnabled && state.clockSecondsEnabled === true
    };
};

const readClockPreferenceState = (preferences: UiPreferences): ClockPreferenceState => {
    return normalizeClockPreferenceState({
        headerClockEnabled: preferences.headerClockEnabled !== false,
        clockSecondsEnabled: preferences.clockSecondsEnabled === true
    });
};

const writeClockPreferenceState = (preferences: UiPreferences, state: ClockPreferenceState): boolean => {
    const normalized = normalizeClockPreferenceState(state);
    const changed = preferences.headerClockEnabled !== normalized.headerClockEnabled || preferences.clockSecondsEnabled !== normalized.clockSecondsEnabled;
    preferences.headerClockEnabled = normalized.headerClockEnabled;
    preferences.clockSecondsEnabled = normalized.clockSecondsEnabled;
    return changed;
};

const clockPreferenceStatesEqual = (left: ClockPreferenceState, right: ClockPreferenceState): boolean => {
    const normalizedLeft = normalizeClockPreferenceState(left);
    const normalizedRight = normalizeClockPreferenceState(right);
    return normalizedLeft.headerClockEnabled === normalizedRight.headerClockEnabled && normalizedLeft.clockSecondsEnabled === normalizedRight.clockSecondsEnabled;
};

const dispatchClockPreferenceChanged = (state: ClockPreferenceState): void => {
    const normalized = normalizeClockPreferenceState(state);
    const detail: JsonObject = {
        headerClockEnabled: normalized.headerClockEnabled,
        clockSecondsEnabled: normalized.clockSecondsEnabled
    };
    dispatchCustomEvent(CLOCK_PREFERENCES_CHANGED_EVENT, detail);
};

export { CLOCK_PREFERENCES_CHANGED_EVENT, clockPreferenceStatesEqual, dispatchClockPreferenceChanged, normalizeClockPreferenceState, readClockPreferenceState, writeClockPreferenceState };
export type { ClockPreferenceState };
