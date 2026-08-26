/* SoAI - Shared storage clock [frontend/assets/ts/core/storage/service/presentationpreferences/clock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dispatchClockPreferenceChanged, normalizeClockPreferenceState, readClockPreferenceState, writeClockPreferenceState } from '@core/storage/clockPreferences.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

const createPresentationClockPreferenceMethods = (
    core: StorageRuntime
): {
    getHeaderClockEnabled: () => boolean;
    getClockSecondsEnabled: () => boolean;
    setClockPreferences: (headerClockEnabled: boolean, clockSecondsEnabled: boolean) => void;
    setHeaderClockEnabled: (enabled: boolean) => void;
    setClockSecondsEnabled: (enabled: boolean) => void;
} => {
    const state = core.state;

    const getHeaderClockEnabled = (): boolean => readClockPreferenceState(state.cache.ui).headerClockEnabled;

    const getClockSecondsEnabled = (): boolean => readClockPreferenceState(state.cache.ui).clockSecondsEnabled;

    const setClockPreferences = (headerClockEnabled: boolean, clockSecondsEnabled: boolean): void => {
        const next = normalizeClockPreferenceState({
            headerClockEnabled,
            clockSecondsEnabled
        });
        if (!writeClockPreferenceState(state.cache.ui, next)) {
            return;
        }
        terminateHandledPromise(core.queuePersist('ui'));
        dispatchClockPreferenceChanged(next);
    };

    const setHeaderClockEnabled = (enabled: boolean): void => {
        setClockPreferences(enabled, state.cache.ui.clockSecondsEnabled === true);
    };

    const setClockSecondsEnabled = (enabled: boolean): void => {
        setClockPreferences(state.cache.ui.headerClockEnabled !== false, enabled);
    };

    return {
        getHeaderClockEnabled,
        getClockSecondsEnabled,
        setClockPreferences,
        setHeaderClockEnabled,
        setClockSecondsEnabled
    };
};

export { createPresentationClockPreferenceMethods };
