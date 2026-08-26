/* SoAI - Shared frontend connection status events [frontend/assets/ts/core/connectionstatus/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { hasOwn, isFunction, isNumber, isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { EVT_DISCO, EVT_UPDATE, STATEFUL_STATUS_EVENTS, MODULE_NAME } from '@core/connectionstatus/constants.ts';
import type { ConnectionEvent, RestartInfo, StatusSnapshot, RestartSubscriber, StatusSubscriber } from '@core/connectionstatus/types.ts';
import { areRestartInfosEqual } from '@core/connectionstatus/health.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';

const getEventType = (eventType: JsonValue | undefined): string => (isString(eventType) ? eventType.toLowerCase() : EVT_UPDATE);

const isStatefulStatusEvent = (eventType: JsonValue | undefined): boolean => isString(eventType) && STATEFUL_STATUS_EVENTS.has(eventType.toLowerCase());

const isEventDisconnected = (eventType: JsonValue | undefined): boolean => getEventType(eventType) === EVT_DISCO;

const connectionSnapshotHasReadyStatus = (eventType: JsonValue | undefined, status: string | null, hasPayload: boolean): boolean => {
    if (!hasPayload) return false;
    if (!isString(status) || status.toLowerCase() !== 'ready') return false;
    return !isString(eventType) || isStatefulStatusEvent(eventType);
};

const buildConnectionEvent = (state: ConnectionStatusState, type: string, data: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null } = {}): ConnectionEvent => {
    const raw = hasOwn(data, 'raw') ? data.raw : null;
    const error = hasOwn(data, 'error') ? data.error : null;
    const attempt = isNumber(data.attempt) ? data.attempt : null;
    const maxAttempts = isNumber(data.maxAttempts) ? data.maxAttempts : null;
    return {
        type,
        eventType: type,
        connected: state.connected,
        status: state.currentStatus,
        systemInfo: state.systemInfo,
        restartInfo: getRestartInfo(state),
        raw: raw ?? null,
        error: error ?? null,
        attempt,
        maxAttempts
    };
};

const emitConnectionStatus = (state: ConnectionStatusState, type: string, data: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null } = {}): void => {
    if (!state.subscribers.size) return;
    const listeners = Array.from(state.subscribers);
    const event = buildConnectionEvent(state, type, data);
    for (const listener of listeners) {
        try {
            listener(event);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(MODULE_NAME, 'Connection status subscriber failed', runtimeError);
        }
    }
};

const subscribeConnectionStatus = (
    state: ConnectionStatusState,
    callback: StatusSubscriber,
    options: { emitCurrent?: boolean } = {},
    callbacks: {
        publishStatusMetric: (stage: string, extra?: JsonObject) => void;
        clearDisconnectTimer: () => void;
        ensureStream: () => Promise<void> | null;
        scheduleDisconnectEvaluation: () => void;
    }
): (() => void) => {
    if (!isFunction(callback)) return () => {};
    state.subscribers.add(callback);
    callbacks.publishStatusMetric('subscriber:update');
    callbacks.clearDisconnectTimer();
    const streamTask = callbacks.ensureStream();
    if (streamTask) {
        void streamTask.catch((error) => {
            const runtimeError = ensureError(error);
            if (isLifecycleCancellationError(runtimeError)) {
                return;
            }
            errorHandler.warn(MODULE_NAME, 'Connection status stream ensure failed for subscriber', runtimeError);
        });
    }

    if (options.emitCurrent !== false) {
        try {
            callback(buildConnectionEvent(state, EVT_UPDATE));
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(MODULE_NAME, 'Connection status subscriber failed', runtimeError);
        }
    }

    return () => {
        state.subscribers.delete(callback);
        callbacks.publishStatusMetric('subscriber:update');
        callbacks.scheduleDisconnectEvaluation();
    };
};

const subscribeRestartUpdates = (
    state: ConnectionStatusState,
    callback: RestartSubscriber,
    options: { immediate?: boolean } = {},
    callbacks: {
        publishStatusMetric: (stage: string, extra?: JsonObject) => void;
    }
): (() => void) => {
    if (!isFunction(callback)) return () => {};
    state.restartSubscribers.add(callback);
    callbacks.publishStatusMetric('subscriber:update');

    if (options.immediate !== false) {
        try {
            callback(getRestartInfo(state));
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(MODULE_NAME, 'Restart subscriber failed', runtimeError);
        }
    }

    return () => {
        state.restartSubscribers.delete(callback);
        callbacks.publishStatusMetric('subscriber:update');
    };
};

const getStatusSnapshot = (state: ConnectionStatusState): StatusSnapshot | null => {
    if (!state.currentStatus) return null;
    return {
        connected: state.connected,
        status: state.currentStatus,
        systemInfo: state.systemInfo,
        restartInfo: getRestartInfo(state)
    };
};

const getRestartInfo = (state: ConnectionStatusState): RestartInfo => ({
    required: state.restartInfo.required,
    timestamp: state.restartInfo.timestamp,
    pid: state.restartInfo.pid,
    reasons: [...state.restartInfo.reasons],
    notifications: state.restartInfo.notifications.map((entry) => ({ ...entry }))
});

const hasPendingRestart = (state: ConnectionStatusState): boolean => state.restartInfo.required || state.restartInfo.notifications.length > 0;

const flushWaiters = (state: ConnectionStatusState): void => {
    if (!state.currentStatus || !state.waiters.length) return;
    const pending = state.waiters.splice(0);
    for (const waiter of pending) {
        try {
            waiter.resolve();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug(MODULE_NAME, 'Waiter resolve failed', runtimeError);
        }
    }
};

const rejectWaiters = (state: ConnectionStatusState, error: Error): void => {
    if (!state.waiters.length) return;
    const pending = state.waiters.splice(0);
    for (const waiter of pending) {
        try {
            waiter.reject(error);
        } catch (rejectError) {
            const runtimeError = ensureError(rejectError);
            errorHandler.debug(MODULE_NAME, 'Waiter reject failed', runtimeError);
        }
    }
};

const notifyRestartSubscribers = (state: ConnectionStatusState): void => {
    if (!state.restartSubscribers.size) return;
    const next = getRestartInfo(state);
    const listeners = Array.from(state.restartSubscribers);
    for (const listener of listeners) {
        try {
            listener(next);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(MODULE_NAME, 'Restart subscriber failed', runtimeError);
        }
    }
};

const isRestartInfoEqual = (state: ConnectionStatusState, next: RestartInfo): boolean => areRestartInfosEqual(state.restartInfo, next);

export { buildConnectionEvent, emitConnectionStatus, subscribeConnectionStatus, subscribeRestartUpdates, getStatusSnapshot, getRestartInfo, getEventType, isEventDisconnected, isStatefulStatusEvent, connectionSnapshotHasReadyStatus, hasPendingRestart, flushWaiters, rejectWaiters, notifyRestartSubscribers, isRestartInfoEqual };
