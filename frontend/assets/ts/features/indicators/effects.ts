/* SoAI - Indicators feature effects [frontend/assets/ts/features/indicators/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { applyStoredLiveStatusOverlayPosition, attachLiveStatusOverlayDrag } from '@features/indicators/drag.ts';
import { createOverlayElements, renderSnapshot, setConnectionStatus, setLastEvent, setLatencyValue, setQueueValue } from '@features/indicators/view.ts';
import { LIVE_STATUS_OVERLAY_REFRESH_INTERVAL_MS } from '@features/indicators/constants.ts';
import { WEBSOCKET_LATENCY_METRIC_NAME } from '@core/websocketclient/constants.ts';
import { normalizeDiagnosticsSnapshot } from '@features/indicators/mappers.ts';
import { getTelemetryServiceFromState, resolveStreamManager } from '@features/indicators/adapters.ts';
import { clearLiveStatusOverlayRefreshHandle, isLiveStatusOverlayGenerationCurrent } from '@features/indicators/state.ts';
import type { DiagnosticsSnapshot, TelemetryEvent, TelemetryMetric, LiveStatusOverlayErrorReporter, LiveStatusOverlayState } from '@features/indicators/types.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface RefreshContext {
    state: LiveStatusOverlayState;
    reportError: LiveStatusOverlayErrorReporter;
    timers: ResourceTracker;
    generation: number;
}

const ensureOverlayContainer = (state: LiveStatusOverlayState): void => {
    if (state.container && state.container.isConnected && state.statusElement && state.latencyElement && state.queueElement && state.eventElement && state.bundleContainer) {
        return;
    }

    const nodes = createOverlayElements();
    getLayoutRuntimeManager().appendToBody(nodes.container);
    state.container = nodes.container;
    state.statusElement = nodes.statusElement;
    state.latencyElement = nodes.latencyElement;
    state.queueElement = nodes.queueElement;
    state.eventElement = nodes.eventElement;
    state.bundleContainer = nodes.bundleContainer;
    applyStoredLiveStatusOverlayPosition(state);
};

const detachTelemetrySubscriptions = (state: LiveStatusOverlayState, timers: ResourceTracker): void => {
    while (state.unsubscribers.length > 0) {
        const unsubscribe = state.unsubscribers.pop();
        if (!isFunction(unsubscribe)) {
            continue;
        }
        try {
            unsubscribe();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('LiveStatusOverlay', 'Failed to detach telemetry subscription', runtimeError);
            clearLiveStatusOverlayRefreshHandle(state, timers);
        }
    }
};

const updateConnectionStatus = (state: LiveStatusOverlayState, reportError: LiveStatusOverlayErrorReporter): void => {
    setConnectionStatus(state.statusElement, state.metrics.connection, reportError);
};

const updateLatency = (state: LiveStatusOverlayState): void => {
    setLatencyValue(state.latencyElement, state.metrics.latency);
};

const updateQueueStatus = (state: LiveStatusOverlayState): void => {
    setQueueValue(state.queueElement, state.metrics.queue);
};

const updateLastEvent = (state: LiveStatusOverlayState): void => {
    setLastEvent(state.eventElement, state.lastEvent);
};

const renderOverlaySnapshot = (state: LiveStatusOverlayState, snapshot: DiagnosticsSnapshot): void => {
    renderSnapshot(state.bundleContainer, snapshot);
};

const clearTelemetryState = (state: LiveStatusOverlayState): void => {
    state.metrics = {
        connection: null,
        latency: null,
        queue: null
    };
    state.lastEvent = null;
};

const refreshDiagnostics = async (context: RefreshContext): Promise<void> => {
    const { state, reportError, generation } = context;
    if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
        return;
    }

    const manager = await resolveStreamManager(state);
    if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
        return;
    }
    const rawSnapshot = manager.getDiagnostics();
    if (!isObject(rawSnapshot)) {
        throw new Error('Stream manager diagnostics must return an object');
    }

    const snapshot = normalizeDiagnosticsSnapshot(rawSnapshot);
    const queueDepth = snapshot.queueDepth;
    if (!state.metrics.queue) {
        const telemetryService = getTelemetryServiceFromState(state);
        telemetryService.publishMetric('stream.queueDepth', queueDepth ?? 0, {
            source: 'telemetry.overlay'
        });
    }

    renderOverlaySnapshot(state, { queueDepth, bundles: snapshot.bundles });
    updateConnectionStatus(state, reportError);
    updateLatency(state);
    updateQueueStatus(state);
    updateLastEvent(state);
};

const scheduleDiagnosticsRefresh = (context: RefreshContext): void => {
    const { state, reportError, timers, generation } = context;
    if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
        return;
    }
    clearLiveStatusOverlayRefreshHandle(state, timers);
    state.refreshHandle = timers.setTimeout((): void => {
        state.refreshHandle = null;
        void requestDiagnosticsRefresh(context).catch((error): void => {
            reportError('Failed to refresh telemetry diagnostics', ensureError(error), 'error');
        });
    }, LIVE_STATUS_OVERLAY_REFRESH_INTERVAL_MS);
};

const drainDiagnosticsRefreshes = async (context: RefreshContext): Promise<void> => {
    const { state, generation } = context;
    try {
        while (state.refreshRequested && isLiveStatusOverlayGenerationCurrent(state, generation)) {
            state.refreshRequested = false;
            await refreshDiagnostics(context);
        }
    } finally {
        scheduleDiagnosticsRefresh(context);
    }
};

const requestDiagnosticsRefresh = async (context: RefreshContext): Promise<void> => {
    const { state, timers, generation } = context;
    clearLiveStatusOverlayRefreshHandle(state, timers);
    if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
        return;
    }
    state.refreshRequested = true;
    if (state.refreshTask && state.refreshTaskGeneration === generation) {
        await state.refreshTask;
        return;
    }
    const refreshTask = drainDiagnosticsRefreshes(context).finally((): void => {
        if (state.refreshTask === refreshTask) {
            state.refreshTask = null;
        }
    });
    state.refreshTask = refreshTask;
    state.refreshTaskGeneration = generation;
    await refreshTask;
};

const attachTelemetryObservers = (state: LiveStatusOverlayState, reportError: LiveStatusOverlayErrorReporter, timers: ResourceTracker, generation: number): void => {
    detachTelemetrySubscriptions(state, timers);
    const telemetryService = getTelemetryServiceFromState(state);

    const connectionUnsub = telemetryService.observeMetric('connection.status', (metric: TelemetryMetric): void => {
        if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
            return;
        }
        state.metrics.connection = metric;
        updateConnectionStatus(state, reportError);
    });
    if (isFunction(connectionUnsub)) {
        state.unsubscribers.push(connectionUnsub);
    }

    const latencyUnsub = telemetryService.observeMetric(WEBSOCKET_LATENCY_METRIC_NAME, (metric: TelemetryMetric): void => {
        if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
            return;
        }
        state.metrics.latency = metric;
        updateLatency(state);
    });
    if (isFunction(latencyUnsub)) {
        state.unsubscribers.push(latencyUnsub);
    }

    const queueUnsub = telemetryService.observeMetric('stream.queueDepth', (metric: TelemetryMetric): void => {
        if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
            return;
        }
        state.metrics.queue = metric;
        updateQueueStatus(state);
    });
    if (isFunction(queueUnsub)) {
        state.unsubscribers.push(queueUnsub);
    }

    const eventUnsub = telemetryService.subscribe((event: TelemetryEvent): void => {
        if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
            return;
        }
        if (!isObject(event)) {
            state.lastEvent = null;
            updateLastEvent(state);
            return;
        }

        state.lastEvent = event;
        updateLastEvent(state);

        if (typeof event['stage'] === 'string' && (event['stage'].startsWith('snapshot') || event['stage'].startsWith('bootstrap') || event['stage'].startsWith('connection'))) {
            void requestDiagnosticsRefresh({
                state,
                reportError,
                timers,
                generation
            }).catch((error): void => {
                reportError('Telemetry diagnostics refresh failed', ensureError(error), 'error');
            });
        }
    });
    if (isFunction(eventUnsub)) {
        state.unsubscribers.push(eventUnsub);
    }
};

const activateLiveStatusOverlay = async (state: LiveStatusOverlayState, reportError: LiveStatusOverlayErrorReporter, timers: ResourceTracker, generation: number): Promise<void> => {
    if (state.active) {
        return;
    }

    ensureOverlayContainer(state);
    attachTelemetryObservers(state, reportError, timers, generation);
    attachLiveStatusOverlayDrag(state, timers, generation);
    await resolveStreamManager(state);
    if (!isLiveStatusOverlayGenerationCurrent(state, generation)) {
        return;
    }
    updateConnectionStatus(state, reportError);
    updateLatency(state);
    updateQueueStatus(state);
    updateLastEvent(state);
    renderOverlaySnapshot(state, { queueDepth: null, bundles: [] });

    await requestDiagnosticsRefresh({
        state,
        reportError,
        timers,
        generation
    });
};

const deactivateLiveStatusOverlay = (state: LiveStatusOverlayState, timers: ResourceTracker): void => {
    state.refreshRequested = false;
    clearLiveStatusOverlayRefreshHandle(state, timers);
    detachTelemetrySubscriptions(state, timers);
    if (!state.container) {
        clearTelemetryState(state);
        state.active = false;
        return;
    }

    let removalError: Error | null = null;
    try {
        getLayoutRuntimeManager().removeNode(state.container);
    } catch (error) {
        removalError = ensureError(error);
    } finally {
        state.container = null;
        state.statusElement = null;
        state.latencyElement = null;
        state.queueElement = null;
        state.eventElement = null;
        state.bundleContainer = null;
        clearTelemetryState(state);
        state.dragState = null;
        state.active = false;
    }
    if (removalError) {
        throw removalError;
    }
};

export { activateLiveStatusOverlay, deactivateLiveStatusOverlay };
