/* SoAI - Shared frontend connection status adapters [frontend/assets/ts/core/connectionstatus/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { getStatusStream, readTimer, requireAuthManager, resetStreamManagerCaches, startTimer } from '@core/connectionstatus/deps.ts';
import { EVT_DISCO, EVT_UPDATE, INITIAL_RESTART_DELAY_MS, MODULE_NAME } from '@core/connectionstatus/constants.ts';

import type { EnsureStreamHost, StopStreamHost } from '@core/connectionstatus/internalContracts.ts';
import { ensureError, normalizeErrorTelemetryFields } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';

const readErrorMessage = (payload: JsonValue): string | null => {
    if (!isObject(payload)) return null;
    const message = payload['message'];
    return isString(message) ? message : null;
};

const processConnectionStatusResourceSnapshot = (host: Pick<EnsureStreamHost, 'log' | 'processSnapshot'>, resourceSnapshot: ResourceReconciliationSnapshot): void => {
    if (resourceSnapshot.status === 'disconnected' && resourceSnapshot.transitionType === EVT_DISCO) {
        host.processSnapshot(resourceSnapshot.value, EVT_DISCO);
        return;
    }
    if (resourceSnapshot.status !== 'ready') return;
    const type = resourceSnapshot.transitionType || EVT_UPDATE;
    const snapshotPayload = resourceSnapshot.value;
    host.log('debug', 'Received system status snapshot', {
        eventType: type,
        snapshotType: isObject(snapshotPayload) ? Object.keys(snapshotPayload) : null
    });
    host.processSnapshot(snapshotPayload, type);
};

const ensureConnectionStatusStream = (host: EnsureStreamHost): Promise<void> | null => {
    const state = host.state;
    if (state.maintenanceHold) return null;
    if (state.unsubscribeHub || state.isStarting) {
        return state.streamStartTask ?? (state.unsubscribeHub ? Promise.resolve() : null);
    }

    const authManager = requireAuthManager();
    if (!authManager.isAuthenticated) {
        host.setConnected(false);
        return null;
    }

    const queueDepth = host.readQueueDepth();
    const bootContext = {
        statusSubscribers: state.subscribers.size,
        restartSubscribers: state.restartSubscribers.size,
        waitingResolvers: state.waiters.length
    };
    state.bootstrapTracker = startTimer();
    host.emitTelemetry({
        stage: 'bootstrap:start',
        message: 'System status stream bootstrap started',
        severity: 'info',
        data: {
            queueDepth,
            ...bootContext
        },
        queueDepth
    });
    host.publishMetric('bootstrap:start', bootContext, queueDepth);

    state.isStarting = true;
    state.streamStartTask = (async () => {
        try {
            const managerCandidate = await host.ensureDeclaredResources();
            if (!managerCandidate) {
                return;
            }
            const streamManager: StreamRuntimeOwners = managerCandidate;

            if (!state.subscribers.size && !state.waiters.length && !state.restartSubscribers.size) {
                return;
            }

            const unsubscribe = streamManager.subscriptions.subscribeResourceState(getStatusStream(), (resourceSnapshot) => processConnectionStatusResourceSnapshot(host, resourceSnapshot), { immediate: true });

            if (isFunction(unsubscribe)) {
                state.unsubscribeHub = unsubscribe;
            }

            state.nextRestartDelayMs = INITIAL_RESTART_DELAY_MS;
            host.clearRestartTimer();
            host.emitTelemetry({
                stage: 'bootstrap:complete',
                message: 'System status stream initialized',
                severity: 'info',
                data: {
                    statusSubscribers: state.subscribers.size,
                    restartSubscribers: state.restartSubscribers.size
                }
            });
            host.publishMetric('bootstrap:complete', {
                statusSubscribers: state.subscribers.size,
                restartSubscribers: state.restartSubscribers.size
            });
        } catch (error) {
            host.setConnected(false);
            const runtimeError = ensureError(error);
            if (isLifecycleCancellationError(runtimeError)) {
                host.rejectWaiters(runtimeError);
                return;
            }
            errorHandler.error(MODULE_NAME, 'Stream initialization failed', runtimeError);
            const completeQueueDepth = host.readQueueDepth();
            const payload = normalizeErrorTelemetryFields(runtimeError);
            const duration = readTimer(state.bootstrapTracker);
            host.emitTelemetry({
                stage: 'bootstrap:error',
                message: 'System status stream bootstrap failed',
                severity: 'error',
                data: {
                    error: payload,
                    duration,
                    queueDepth: completeQueueDepth
                },
                queueDepth: completeQueueDepth
            });
            host.publishMetric('bootstrap:error', { error: readErrorMessage(payload) }, completeQueueDepth);
            host.emitTelemetry({
                stage: 'connection:lost',
                message: 'System status stream disconnected during bootstrap',
                severity: 'warn',
                data: { error: payload, reason: 'bootstrap-error' },
                queueDepth: completeQueueDepth
            });
            host.publishMetric('connection:lost', { reason: 'bootstrap-error', error: readErrorMessage(payload) }, completeQueueDepth);
            host.emitEvent('error', { error: runtimeError.message });
            host.rejectWaiters(runtimeError);
            throw runtimeError;
        } finally {
            state.isStarting = false;
            state.streamStartTask = null;
            state.bootstrapTracker = null;
        }
    })();

    return state.streamStartTask;
};

const stopConnectionStatusStream = (host: StopStreamHost): void => {
    const state = host.state;
    state.isStarting = false;
    state.streamStartTask = null;
    host.clearRestartTimer();
    state.nextRestartDelayMs = INITIAL_RESTART_DELAY_MS;
    const queueDepth = host.readQueueDepth();

    host.emitTelemetry({
        stage: 'stream:detached',
        message: 'System status stream stopped',
        severity: 'info',
        data: {
            statusSubscribers: state.subscribers.size,
            restartSubscribers: state.restartSubscribers.size
        },
        queueDepth
    });
    host.publishMetric(
        'stream:detached',
        {
            statusSubscribers: state.subscribers.size,
            restartSubscribers: state.restartSubscribers.size
        },
        queueDepth
    );

    if (isFunction(state.unsubscribeHub)) {
        try {
            state.unsubscribeHub();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(MODULE_NAME, 'Failed to remove connection status subscription', runtimeError);
        }
    }
    state.unsubscribeHub = null;

    if (state.loginListener) {
        try {
            state.loginListener();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug(MODULE_NAME, 'Failed to remove login callback', runtimeError);
        }
    }
    state.loginListener = null;

    if (!state.subscribers.size && !state.restartSubscribers.size) {
        resetStreamManagerCaches();
    }

    if (state.connected) {
        host.emitTelemetry({
            stage: 'connection:lost',
            message: 'System status stream disconnected',
            severity: 'warn',
            data: {
                statusSubscribers: state.subscribers.size,
                restartSubscribers: state.restartSubscribers.size
            },
            queueDepth
        });
        host.publishMetric(
            'connection:lost',
            {
                statusSubscribers: state.subscribers.size,
                restartSubscribers: state.restartSubscribers.size
            },
            queueDepth
        );
        host.setConnected(false);
        host.emitEvent(EVT_DISCO, { raw: null });
        host.resetRestartInfoState({ reason: 'stream-disconnected' });
    }

    if (state.waiters.length) {
        host.rejectWaiters(new Error('Connection status stream stopped'));
    }
};

export { ensureConnectionStatusStream, processConnectionStatusResourceSnapshot, stopConnectionStatusStream };
