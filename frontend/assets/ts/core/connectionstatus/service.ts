/* SoAI - Shared frontend connection status service [frontend/assets/ts/core/connectionstatus/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { createModuleLogger, type ModuleLogger } from '@core/runtime/runtimeContext.ts';
import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { isFunction, isNumber, isObject, isString } from '@core/typeGuards.ts';
import { getStatusStream, readTimer, requireAuthManager } from '@core/connectionstatus/deps.ts';
import { clearDisconnectTimer, clearRestartTimer, hasActiveConsumers, scheduleDisconnectEvaluation, scheduleStreamRestart, retainConnection, releaseConnection, resetRestartInfoState } from '@core/connectionstatus/actions.ts';
import { emitConnectionStatus, getStatusSnapshot, notifyRestartSubscribers, rejectWaiters, subscribeConnectionStatus, subscribeRestartUpdates } from '@core/connectionstatus/events.ts';
import { emitConnectionStatusTelemetry } from '@core/connectionstatus/effects.ts';
import { DEFAULT_INITIAL_SNAPSHOT_TIMEOUT_MS, DISCONNECT_EVAL_DELAY_MS, MODULE_NAME, REASON_MAIN, SRC } from '@core/connectionstatus/constants.ts';
import { ensureConnectionStatusStream, stopConnectionStatusStream } from '@core/connectionstatus/adapters.ts';
import { waitForInitialConnectionSnapshot } from '@core/connectionstatus/initialSnapshot.ts';
import { processConnectionStatusSnapshot } from '@core/connectionstatus/mappers.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import { emitConnectionStatusServiceError, publishStatusMetricState, readConnectionStatusQueueDepth } from '@core/connectionstatus/serviceDiagnostics.ts';
import { createConnectionStatusServiceHosts, type ConnectionStatusServiceHosts } from '@core/connectionstatus/serviceHosts.ts';
import { resetConnectionStatusSession } from '@core/connectionstatus/sessionReset.ts';
import { createConnectionStatusState, type ConnectionStatusState } from '@core/connectionstatus/state.ts';
import type { HoldOptions, InitialSnapshotOptions, MaintenanceState, SubscribeConnectionOptions, SubscribeRestartOptions } from '@core/connectionstatus/contracts.ts';
import type { RestartSubscriber, StatusSnapshot, StatusSubscriber } from '@core/connectionstatus/types.ts';
import { clearDeferredSessionActivation } from '@core/auth/sessionActivation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
const log: ModuleLogger = createModuleLogger(MODULE_NAME, { defaultLevel: 'debug' });
class ConnectionStatus extends LifecycleModel {
    #state: ConnectionStatusState;
    constructor() {
        super({ name: SRC, type: 'service', moduleId: SRC });
        this.#state = createConnectionStatusState();
        this.#state.maintenanceUnsubscribe = getMaintenanceCoordinator().subscribe((state: MaintenanceState) => {
            if (state.pausesTransport) {
                this.#state.maintenanceHold = true;
                this.stopStream();
                this.setConnected(false);
                this.resetRestartInfoState({ reason: REASON_MAIN });
            } else {
                this.#state.maintenanceHold = false;
                if (this.hasActiveConsumers()) {
                    this.ensureStreamSafely('maintenance-resume');
                }
            }
        });
    }
    override getRequiredResources(): string[] {
        return [getStatusStream()];
    }
    private emitTelemetry(stage: string, message: string, severity: 'debug' | 'info' | 'warn' | 'error', data: JsonValue = null, queueDepth?: number | null): void {
        const safeQueueDepth = isNumber(queueDepth) ? queueDepth : null;
        emitConnectionStatusTelemetry(stage, message, severity, data, { duration: readTimer(this.#state.bootstrapTracker), queueDepth: safeQueueDepth });
    }
    private readQueueDepth(): number | null {
        return readConnectionStatusQueueDepth(MODULE_NAME);
    }
    private setConnected(value: boolean): void {
        this.#state.connected = !!value;
    }
    private emitConnectionError(error: Error, reason: string): void {
        emitConnectionStatusServiceError(
            this.#state,
            error,
            reason,
            () => this.readQueueDepth(),
            (stage, message, severity, data = null, options = {}) => {
                this.emitTelemetry(stage, message, severity, data, options.queueDepth ?? null);
            }
        );
    }
    isConnected(): boolean {
        return this.#state.connected;
    }
    private emitEvent(type: string, data: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null } = {}): void {
        emitConnectionStatus(this.#state, type, data);
    }
    private hasActiveConsumers(includeWaiters = true): boolean {
        return hasActiveConsumers(this.#state, includeWaiters);
    }
    private clearDisconnectTimer(): void {
        clearDisconnectTimer(this.#state, (timerId) => this.lifecycleResources.clearTimer(timerId));
    }
    private clearRestartTimer(): void {
        clearRestartTimer(this.#state, (timerId) => this.lifecycleResources.clearTimer(timerId));
    }
    private scheduleDisconnectEvaluation(delayMs: number = DISCONNECT_EVAL_DELAY_MS): void {
        scheduleDisconnectEvaluation(
            this.#state,
            { isMaintenanceHold: () => this.#state.maintenanceHold, isStarting: () => this.#state.isStarting, hasHub: () => this.#state.unsubscribeHub !== null, hasActiveConsumers: () => this.hasActiveConsumers(), setTimer: (handler, delay) => this.lifecycleResources.setTimer(handler, delay), clearTimer: (timerId) => this.lifecycleResources.clearTimer(timerId), ensureStream: () => this.ensureStream(), setNextRestartDelayMs: () => undefined },
            () => {
                this.stopStream();
            },
            delayMs
        );
    }
    private scheduleStreamRestart(delayMs: number = this.#state.nextRestartDelayMs): void {
        scheduleStreamRestart(
            this.#state,
            {
                isMaintenanceHold: () => this.#state.maintenanceHold,
                isStarting: () => this.#state.isStarting,
                hasHub: () => this.#state.unsubscribeHub !== null,
                hasActiveConsumers: () => this.hasActiveConsumers(),
                setTimer: (handler, delay) => this.lifecycleResources.setTimer(handler, delay),
                clearTimer: (timerId) => this.lifecycleResources.clearTimer(timerId),
                ensureStream: () => this.ensureStream(),
                setNextRestartDelayMs: (nextDelay) => {
                    this.#state.nextRestartDelayMs = nextDelay;
                },
                onRestartFailure: (error) => {
                    this.emitConnectionError(error, 'System status restart attempt failed');
                }
            },
            delayMs
        );
    }
    private createServiceHosts(): ConnectionStatusServiceHosts {
        return createConnectionStatusServiceHosts({
            state: this.#state,
            log,
            ensureDeclaredResources: async (): Promise<StreamRuntimeOwners | null> => this.ensureDeclaredResources({ allowDiscovery: true, strict: true }),
            ensureStream: () => this.ensureStream(),
            processSnapshot: (snapshot: JsonValue, eventType: string): void => this.processSnapshot(snapshot, eventType),
            setConnected: (value: boolean): void => this.setConnected(value),
            readQueueDepth: (): number | null => this.readQueueDepth(),
            clearRestartTimer: (): void => this.clearRestartTimer(),
            scheduleStreamRestart: (): void => this.scheduleStreamRestart(),
            emitTelemetry: (stage, message, severity, data, queueDepth): void => this.emitTelemetry(stage, message, severity, data, queueDepth),
            publishMetric: (stage, extra, queueDepth): void => publishStatusMetricState(this.#state, stage, extra || {}, queueDepth),
            emitEvent: (type, data): void => this.emitEvent(type, data || {}),
            emitConnectionError: (error: Error, reason: string): void => this.emitConnectionError(error, reason),
            resetRestartInfoState: (context = {}): void => this.resetRestartInfoState(context),
            rejectWaiters: (error: Error): void => rejectWaiters(this.#state, error)
        });
    }
    ensureStream(): Promise<void> | null {
        return ensureConnectionStatusStream(this.createServiceHosts().ensureStream);
    }
    private stopStream(): void {
        stopConnectionStatusStream(this.createServiceHosts().stopStream);
    }
    private processSnapshot(snapshot: JsonValue, eventType: string): void {
        processConnectionStatusSnapshot(this.createServiceHosts().snapshotProcessing, snapshot, eventType);
    }
    subscribe(callback: StatusSubscriber, options: SubscribeConnectionOptions = {}): () => void {
        return subscribeConnectionStatus(this.#state, callback, options, { publishStatusMetric: (stage, extra) => publishStatusMetricState(this.#state, stage, extra || {}), clearDisconnectTimer: () => this.clearDisconnectTimer(), ensureStream: () => this.ensureStream(), scheduleDisconnectEvaluation: () => this.scheduleDisconnectEvaluation() });
    }
    onChange(listener: StatusSubscriber, options: SubscribeConnectionOptions = {}): () => void {
        if (!isFunction(listener)) {
            throw new TypeError('Connection status change listener must be a function');
        }
        return this.subscribe(listener, options);
    }
    getSnapshot(): StatusSnapshot | null {
        return getStatusSnapshot(this.#state);
    }
    async getInitialSnapshot(options: InitialSnapshotOptions = {}): Promise<StatusSnapshot | null> {
        const timeout = isNumber(options.timeout) && Number.isFinite(options.timeout) ? options.timeout : DEFAULT_INITIAL_SNAPSHOT_TIMEOUT_MS;
        return waitForInitialConnectionSnapshot({
            timeout,
            hasCurrentStatus: () => this.#state.currentStatus !== null,
            getSnapshot: () => this.getSnapshot(),
            isAuthenticated: () => requireAuthManager().isAuthenticated,
            setTimer: (handler, delay) => this.lifecycleResources.setTimer(handler, delay),
            clearTimer: (timerId) => this.lifecycleResources.clearTimer(timerId),
            addWaiter: (waiter) => {
                this.#state.waiters.push(waiter);
            },
            ensureStream: () => this.ensureStream()
        });
    }
    subscribeRestart(callback: RestartSubscriber, options: SubscribeRestartOptions = {}): () => void {
        return subscribeRestartUpdates(this.#state, callback, options, { publishStatusMetric: (stage, extra) => publishStatusMetricState(this.#state, stage, extra || {}) });
    }
    retainConnection(label: string = 'anonymous', options: HoldOptions = {}): symbol {
        const safeLabel = isString(label) && label.trim() ? label.trim() : 'anonymous';
        const token = retainConnection(
            this.#state,
            safeLabel,
            options,
            (handler, delay) => this.lifecycleResources.setTimer(handler, delay),
            (connectionToken) => {
                this.releaseConnection(connectionToken, { reason: 'timeout' });
            }
        );
        publishStatusMetricState(this.#state, 'hold:acquired', { holds: this.#state.connectionHolds.size, label: safeLabel });
        this.clearDisconnectTimer();
        this.ensureStreamSafely('hold-retained');
        return token;
    }
    releaseConnection(token: symbol, context: { reason?: string } = {}): boolean {
        if (!token || !releaseConnection(this.#state, token, (timerId) => this.lifecycleResources.clearTimer(timerId))) {
            return false;
        }
        publishStatusMetricState(this.#state, 'hold:released', { holds: this.#state.connectionHolds.size, reason: isString(context.reason) ? context.reason : null });
        this.scheduleDisconnectEvaluation();
        return true;
    }
    releaseAllConnectionHolds(reason: string = 'cleanup'): void {
        const tokens = Array.from(this.#state.connectionHolds.keys());
        for (const token of tokens) {
            this.releaseConnection(token, { reason });
        }
    }
    reset(): void {
        resetConnectionStatusSession({
            state: this.#state,
            stopStream: () => this.stopStream(),
            clearLoginListener: () => {
                clearDeferredSessionActivation({
                    getCurrentListener: () => this.#state.loginListener,
                    setCurrentListener: (listener) => {
                        this.#state.loginListener = listener;
                    },
                    onCleanupError: (error) => {
                        errorHandler.debug(MODULE_NAME, 'Failed to remove login callback', error);
                    }
                });
            },
            clearDisconnectTimer: () => this.clearDisconnectTimer(),
            clearRestartTimer: () => this.clearRestartTimer(),
            releaseAllConnectionHolds: () => this.releaseAllConnectionHolds('reset'),
            rejectWaiters: (error) => rejectWaiters(this.#state, error),
            resetRestartInfoState: () => this.resetRestartInfoState({ reason: 'session-reset' })
        });
    }
    private resetRestartInfoState(context: JsonObject = {}): void {
        if (!resetRestartInfoState(this.#state)) return;
        log('info', 'Reset restart info state', isObject(context) ? context : {});
        if (this.#state.restartSubscribers.size) {
            notifyRestartSubscribers(this.#state);
        }
    }
    private ensureStreamSafely(reason: string): void {
        const task = this.ensureStream();
        if (!task) {
            return;
        }
        void task.catch((error) => {
            const runtimeError = ensureError(error);
            if (isLifecycleCancellationError(runtimeError)) {
                return;
            }
            errorHandler.warn(MODULE_NAME, `System status stream ensure failed (${reason})`, runtimeError);
        });
    }
    override async onDestroy(): Promise<void> {
        if (this.#state.maintenanceUnsubscribe) {
            this.#state.maintenanceUnsubscribe();
            this.#state.maintenanceUnsubscribe = null;
        }
        this.releaseAllConnectionHolds('destroy');
        this.clearDisconnectTimer();
        this.clearRestartTimer();
        await super.onDestroy();
    }
}
export { ConnectionStatus };
