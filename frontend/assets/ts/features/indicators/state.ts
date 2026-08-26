/* SoAI - Indicators feature state [frontend/assets/ts/features/indicators/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LiveStatusOverlayState } from '@features/indicators/types.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

const createLiveStatusOverlayState = (): LiveStatusOverlayState => ({
    container: null,
    statusElement: null,
    latencyElement: null,
    queueElement: null,
    eventElement: null,
    bundleContainer: null,
    unsubscribers: [],
    metrics: {
        connection: null,
        latency: null,
        queue: null
    },
    lastEvent: null,
    streamManager: null,
    refreshHandle: null,
    refreshTask: null,
    refreshTaskGeneration: 0,
    refreshRequested: false,
    lifecycleGeneration: 0,
    destroyed: false,
    storage: null,
    telemetry: null,
    enabled: false,
    position: null,
    dragState: null,
    active: false,
    settingListenerRegistered: false
});

const isLiveStatusOverlayGenerationCurrent = (state: LiveStatusOverlayState, generation: number): boolean => {
    return state.enabled && !state.destroyed && state.lifecycleGeneration === generation;
};

const clearLiveStatusOverlayRefreshHandle = (state: LiveStatusOverlayState, timers: ResourceTracker): void => {
    if (!state.refreshHandle) {
        return;
    }
    timers.clearTimer(state.refreshHandle);
    state.refreshHandle = null;
};

const resetTelemetryMetrics = (state: LiveStatusOverlayState): void => {
    state.metrics = {
        connection: null,
        latency: null,
        queue: null
    };
    state.lastEvent = null;
};

export { clearLiveStatusOverlayRefreshHandle, createLiveStatusOverlayState, isLiveStatusOverlayGenerationCurrent, resetTelemetryMetrics };
