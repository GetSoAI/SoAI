/* SoAI - Shared frontend connection status actions [frontend/assets/ts/core/connectionstatus/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isNumber, isObject, isString } from '@core/typeGuards.ts';
import { EVT_DISCO, STATEFUL_STATUS_EVENTS } from '@core/connectionstatus/constants.ts';
import { nextDelayMs, normalizeDelayMs } from '@core/connectionstatus/retries.ts';
import { createDefaultRestartInfo, hasSystemStateKey, normalizeRestartInfo, areRestartInfosEqual } from '@core/connectionstatus/health.ts';
import { type ConnectionHold } from '@core/connectionstatus/types.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RestartHost {
    isMaintenanceHold: () => boolean;
    isStarting: () => boolean;
    hasHub: () => boolean;
    hasActiveConsumers: (includeWaiters?: boolean) => boolean;
    setTimer: (handler: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null) => void;
    ensureStream: () => Promise<void> | null;
    setNextRestartDelayMs: (delayMs: number) => void;
    onRestartFailure?: (error: Error, nextDelay: number) => void;
}

const isStatefulStatusEvent = (eventType: JsonValue): boolean => isString(eventType) && STATEFUL_STATUS_EVENTS.has(eventType.toLowerCase());

const connectionSnapshotHasReadyStatus = (eventType: JsonValue, status: string | null, hasPayload: boolean): boolean => {
    if (!hasPayload) return false;
    if (!isString(status) || status.toLowerCase() !== 'ready') return false;
    return !isString(eventType) || isStatefulStatusEvent(eventType);
};

const hasActiveConsumers = (state: ConnectionStatusState, includeWaiters = true): boolean => {
    let count = state.subscribers.size + state.restartSubscribers.size + state.connectionHolds.size;
    if (includeWaiters) count += state.waiters.length;
    return count > 0;
};

const clearDisconnectTimer = (state: ConnectionStatusState, clearTimer: (timerId: number | null) => void): void => {
    if (state.disconnectTimer === null) return;
    clearTimer(state.disconnectTimer);
    state.disconnectTimer = null;
};

const clearRestartTimer = (state: ConnectionStatusState, clearTimer: (timerId: number | null) => void): void => {
    if (state.restartTimer === null) return;
    clearTimer(state.restartTimer);
    state.restartTimer = null;
};

const scheduleDisconnectEvaluation = (state: ConnectionStatusState, host: RestartHost, stopStream: () => void, delayMs: number = 500): void => {
    if (host.hasActiveConsumers(false)) {
        clearDisconnectTimer(state, host.clearTimer);
        return;
    }
    if (state.disconnectTimer !== null) return;

    state.disconnectTimer = host.setTimer(
        () => {
            state.disconnectTimer = null;
            if (!host.hasActiveConsumers(false)) {
                stopStream();
            }
        },
        delayMs > 0 && Number.isFinite(delayMs) ? delayMs : 0
    );
};

const scheduleStreamRestart = (state: ConnectionStatusState, host: RestartHost, delayMs: number = state.nextRestartDelayMs): void => {
    if (host.isMaintenanceHold() || state.restartTimer !== null || host.isStarting() || host.hasHub() || !host.hasActiveConsumers()) {
        return;
    }

    const delay = normalizeDelayMs(delayMs);
    state.restartTimer = host.setTimer(() => {
        state.restartTimer = null;
        if (!host.hasActiveConsumers()) return;

        const task = host.ensureStream();
        if (task) {
            void task.catch((error) => {
                const runtimeError = ensureError(error);
                const next = nextDelayMs(delay);
                host.setNextRestartDelayMs(next);
                if (isFunction(host.onRestartFailure)) {
                    host.onRestartFailure(runtimeError, next);
                }
                scheduleStreamRestart(state, host, next);
            });
        }
    }, delay);
};

const retainConnection = (state: ConnectionStatusState, label: string, normalizedOptions: { timeoutMs?: number }, setTimer: (handler: () => void, delay: number) => number | null, onTimeout: (token: symbol) => void): symbol => {
    const resolvedLabel = isString(label) && label.trim() ? label.trim() : 'anonymous';
    const timeoutMs = isNumber(normalizedOptions.timeoutMs) && Number.isFinite(normalizedOptions.timeoutMs) && normalizedOptions.timeoutMs > 0 ? normalizedOptions.timeoutMs : null;
    const token = Symbol(resolvedLabel);
    const now = Date.now();
    const hold: ConnectionHold = { label: resolvedLabel, createdAt: now, timer: null };
    if (timeoutMs !== null) {
        hold.expiresAtMs = now + timeoutMs;
        hold.timer = setTimer(() => onTimeout(token), timeoutMs);
    }
    state.connectionHolds.set(token, hold);
    return token;
};

const releaseConnection = (state: ConnectionStatusState, token: symbol, clearTimer: (timerId: number | null) => void): boolean => {
    const hold = state.connectionHolds.get(token);
    if (!hold) return false;
    if (hold.timer !== null) clearTimer(hold.timer);
    state.connectionHolds.delete(token);
    return true;
};

const releaseAllConnectionHolds = (state: ConnectionStatusState, clearTimer: (timerId: number | null) => void): void => {
    const tokens = Array.from(state.connectionHolds.keys());
    for (const token of tokens) {
        releaseConnection(state, token, clearTimer);
    }
};

const isDisconnectedEvent = (eventType: JsonValue): boolean => isString(eventType) && eventType.toLowerCase() === EVT_DISCO;

const updateRestartInfo = (
    state: ConnectionStatusState,
    systemState: JsonObject | null,
    context: {
        normalizedPayload: JsonObject | null;
        rawPayload: JsonValue | undefined;
        snapshotStatus: string | null;
        eventType: string | null;
    }
): boolean => {
    const hasPayload = Boolean(context.normalizedPayload) || isObject(context.rawPayload);
    const hasSystemState = hasSystemStateKey(context.normalizedPayload) || hasSystemStateKey(context.rawPayload);
    const status = isString(context.snapshotStatus) ? context.snapshotStatus : null;

    if (!systemState) {
        if (hasSystemState) {
            throw new Error('System status snapshot contains invalid restart info');
        }
        if (connectionSnapshotHasReadyStatus(context.eventType, status, hasPayload)) {
            return false;
        }
        return false;
    }

    const next = normalizeRestartInfo(systemState);
    if (areRestartInfosEqual(state.restartInfo, next)) return false;
    state.restartInfo = next;
    return true;
};

const resetRestartInfoState = (state: ConnectionStatusState): boolean => {
    const next = createDefaultRestartInfo();
    if (areRestartInfosEqual(state.restartInfo, next)) return false;
    state.restartInfo = next;
    return true;
};

export { isStatefulStatusEvent, connectionSnapshotHasReadyStatus, hasActiveConsumers, clearDisconnectTimer, clearRestartTimer, scheduleDisconnectEvaluation, scheduleStreamRestart, retainConnection, releaseConnection, releaseAllConnectionHolds, isDisconnectedEvent, updateRestartInfo, resetRestartInfoState };

export type { RestartHost };
