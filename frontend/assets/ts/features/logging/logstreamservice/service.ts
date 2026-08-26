/* SoAI - Logging feature log stream service [frontend/assets/ts/features/logging/logstreamservice/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleModel } from '@core/LifecycleModel.ts';
import type { TelemetryFields } from '@core/telemetry/contracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { TabStatePayload } from '@core/state/TabStateCoordinator.ts';
import { isFunction } from '@core/typeGuards.ts';
import { notifySubscribers, replayBufferToSubscriber, updateCurrentBufferSize, validateReplayLimit } from '@features/logging/logstreamservice/actions.ts';
import { cleanStr, DEFAULT_LOG_SOURCE, LOG_RESOURCE_NAME, LOG_STREAM_SERVICE_ID, MODULE_ID } from '@features/logging/logstreamservice/constants.ts';
import { ensureLogStreamConnection } from '@features/logging/logstreamservice/connection.ts';
import { createLogStreamLogger, createLogStreamRuntimeDependencies } from '@features/logging/logstreamservice/contracts.ts';
import { applyResolvedSnapshot, buildSnapshotResolver, cancelPendingSharedSync, flushSharedBufferToState, handleTabStateChange, restoreBufferFromState, scheduleSharedBufferSync } from '@features/logging/logstreamservice/effects.ts';
import { teardownStreamConnection, type StreamConnectionContext, type StreamUpdateContext } from '@features/logging/logstreamservice/events.ts';
import { ensureHistoricalCoverage } from '@features/logging/logstreamservice/historyExpansion.ts';
import { subscribeLogStreamMaintenance } from '@features/logging/logstreamservice/maintenance.ts';
import type { ConnectionEvent, ConnectionStatus, LogApi, LogStreamEvent, LogStreamListener, LogSubscriberOptions, SnapshotPayload, StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';
import { createLogStreamMutableState, resetMutableStateAfterDestroy, type LogStreamMutableState } from '@features/logging/logstreamservice/state.ts';
class LogStream extends LifecycleModel {
    readonly #api: LogApi;
    private readonly dependencies;
    private readonly logger;
    readonly #states: Map<string, LogStreamMutableState> = new Map();
    #stateSubscription: (() => void) | null = null;
    constructor(inputArguments: { api: LogApi }) {
        super({ name: MODULE_ID, type: 'service' });
        this.#api = inputArguments.api;
        this.dependencies = createLogStreamRuntimeDependencies();
        this.logger = createLogStreamLogger(this.dependencies.errorHandler);
        this.#stateSubscription = this.dependencies.stateService.subscribeTabState((payload) => {
            this.handleTabStateChange(payload);
        });
        this.getSourceState(DEFAULT_LOG_SOURCE);
    }
    override getRequiredResources(): string[] {
        return [LOG_RESOURCE_NAME];
    }
    subscribe(callback: LogStreamListener, options: LogSubscriberOptions = {}): () => void {
        if (this.isDestroyed) {
            throw new Error('Cannot subscribe to a destroyed log stream.');
        }
        if (!isFunction(callback)) {
            throw new Error('Subscriber callback must be a function');
        }
        const source = this.resolveSource(options.source);
        const state = this.getSourceState(source);
        const replayLimit = validateReplayLimit(this.dependencies.validator, options.replayLimit, this.logger);
        state.subscribers.set(callback, replayLimit);
        this.updateBufferSize(state);
        if (!state.replayedSubscribers.has(callback)) {
            const bufferedEnough = state.logBuffer.length >= replayLimit;
            if (bufferedEnough && state.logBuffer.length > 0) {
                replayBufferToSubscriber(state, callback, replayLimit);
                state.replayedSubscribers.add(callback);
            } else {
                void this.ensureHistoricalCoverageForSource(state, replayLimit)
                    .then(() => {
                        if (!state.subscribers.has(callback)) {
                            return;
                        }
                        if (state.replayedSubscribers.has(callback)) {
                            return;
                        }
                        const currentLimit = state.subscribers.get(callback);
                        if (!currentLimit || state.logBuffer.length === 0) {
                            return;
                        }
                        replayBufferToSubscriber(state, callback, currentLimit);
                        state.replayedSubscribers.add(callback);
                    })
                    .catch((error) => {
                        this.logger.logWarn('Failed to load historical logs', error);
                    });
            }
        }
        if (state.isConnected) {
            notifySubscribers(
                state,
                {
                    type: 'connection',
                    status: 'connected',
                    source: state.snapshotMeta.source
                },
                this.logger,
                this.publishMetric
            );
        }
        this.ensureConnection(state).catch((error) => {
            if (state.recoverySuspended) {
                return;
            }
            this.logger.logError('Failed to start stream', error);
        });
        return () => this.unsubscribe(state, callback);
    }
    private unsubscribe(state: LogStreamMutableState, callback: LogStreamListener): void {
        state.subscribers.delete(callback);
        state.replayedSubscribers.delete(callback);
        this.updateBufferSize(state);
        if (state.subscribers.size === 0) {
            this.teardownConnection(state);
            if (state.snapshotMeta.source !== DEFAULT_LOG_SOURCE) {
                this.destroySourceState(state);
                this.#states.delete(state.snapshotMeta.source);
            }
        }
    }
    private handleTabStateChange(payload: TabStatePayload): void {
        this.#states.forEach((state) => {
            const changed = handleTabStateChange(state, payload, this.dependencies.validator, { logError: this.logger.logError }, this.createSnapshotResolver(state));
            if (changed) {
                this.syncSharedBuffer(state, false);
            }
        });
    }
    private syncSharedBuffer(state: LogStreamMutableState, force: boolean): void {
        if (state.snapshotMeta.source !== DEFAULT_LOG_SOURCE) {
            cancelPendingSharedSync(state, (timerId: number): void => {
                this.lifecycleResources.clearTimer(timerId);
            });
            return;
        }
        scheduleSharedBufferSync(
            state,
            force,
            (callback: () => void, delayMs: number) => this.lifecycleResources.setTimer(callback, delayMs),
            (timerId: number): void => {
                this.lifecycleResources.clearTimer(timerId);
            },
            () => this.flushSharedBuffer(state)
        );
    }
    private flushSharedBuffer(state: LogStreamMutableState): void {
        if (state.snapshotMeta.source !== DEFAULT_LOG_SOURCE) {
            return;
        }
        flushSharedBufferToState(state, this.dependencies.stateService, (timerId: number): void => {
            this.lifecycleResources.clearTimer(timerId);
        });
    }
    private updateBufferSize(state: LogStreamMutableState): void {
        updateCurrentBufferSize(
            state,
            async (targetLimit: number) => this.ensureHistoricalCoverageForSource(state, targetLimit),
            () => this.syncSharedBuffer(state, false)
        );
    }
    private async ensureConnection(state: LogStreamMutableState): Promise<StreamSubscriptionHandle | null> {
        return ensureLogStreamConnection({
            state,
            logger: this.logger,
            publishMetric: this.publishMetric,
            ensureDeclaredResources: async (): Promise<void> => {
                await this.ensureDeclaredResources({ allowDiscovery: true, strict: true });
            },
            applySnapshot: (value: JsonValue | null | undefined): void => {
                this.applySnapshot(state, value);
            },
            createStreamUpdateContext: (): StreamUpdateContext => this.createStreamUpdateContext(state),
            createStreamConnectionContext: (connectionGeneration?: number): StreamConnectionContext => this.createStreamConnectionContext(state, connectionGeneration)
        });
    }
    private applySnapshot(state: LogStreamMutableState, snapshot: JsonValue | null | undefined): void {
        const resolved = this.createSnapshotResolver(state)(snapshot);
        if (!resolved) {
            return;
        }
        if (resolved.source !== state.snapshotMeta.source) {
            return;
        }
        applyResolvedSnapshot(state, resolved, () => this.syncSharedBuffer(state, false), this.publishMetric);
    }
    private teardownConnection(state: LogStreamMutableState): void {
        teardownStreamConnection(this.createStreamConnectionContext(state), state.connectionHandle, state.streamManager);
    }
    private createStreamUpdateContext(state: LogStreamMutableState): StreamUpdateContext {
        return {
            state,
            normalizer: this.dependencies.normalizer,
            validator: this.dependencies.validator,
            logger: this.logger,
            publishMetric: this.publishMetric,
            syncSharedBuffer: () => this.syncSharedBuffer(state, false)
        };
    }
    private createStreamConnectionContext(state: LogStreamMutableState, connectionGeneration: number = state.connectionGeneration): StreamConnectionContext {
        return {
            state,
            connectionGeneration,
            logger: this.logger,
            publishMetric: this.publishMetric,
            notify: (event: LogStreamEvent): void => {
                notifySubscribers(state, event, this.logger, this.publishMetric);
            },
            teardownConnection: (): void => {
                this.teardownConnection(state);
            },
            ensureConnection: async (): Promise<StreamSubscriptionHandle | null> => this.ensureConnection(state),
            clearTimer: (timerId: number | null | undefined): void => {
                if (timerId !== null && timerId !== undefined) {
                    this.lifecycleResources.clearTimer(timerId);
                }
            },
            setTimer: (callback: () => void, delayMs: number): number | null => this.lifecycleResources.setTimer(callback, delayMs)
        };
    }
    private async ensureHistoricalCoverageForSource(state: LogStreamMutableState, targetLimit: number): Promise<void> {
        await ensureHistoricalCoverage(
            {
                state,
                validator: this.dependencies.validator,
                normalizer: this.dependencies.normalizer,
                logger: this.logger,
                syncSharedBuffer: () => this.syncSharedBuffer(state, false),
                publishMetric: this.publishMetric,
                ensureConnection: async (): Promise<StreamSubscriptionHandle | null> => this.ensureConnection(state)
            },
            targetLimit
        );
    }
    private getSourceState(source: string): LogStreamMutableState {
        const existing = this.#states.get(source);
        if (existing) {
            return existing;
        }
        const state = createLogStreamMutableState(source);
        state.api = this.#api;
        state.maintenanceSubscription = subscribeLogStreamMaintenance(this.dependencies.maintenanceCoordinator, this.createStreamConnectionContext(state));
        restoreBufferFromState(state, this.dependencies.stateService, this.createSnapshotResolver(state));
        this.#states.set(source, state);
        return state;
    }
    private createSnapshotResolver(state: LogStreamMutableState): (payload: JsonValue | null | undefined) => SnapshotPayload | null {
        return buildSnapshotResolver(state, {
            normalizeLogEntry: (entry: JsonValue | null | undefined) => this.dependencies.normalizer.normalizeLogEntry(entry),
            logger: { logWarn: this.logger.logWarn }
        });
    }
    private resolveSource(source: JsonValue | null | undefined): string {
        return cleanStr(source) ?? DEFAULT_LOG_SOURCE;
    }
    private destroySourceState(state: LogStreamMutableState): void {
        if (isFunction(state.maintenanceSubscription)) {
            state.maintenanceSubscription();
            state.maintenanceSubscription = null;
        }
        if (state.snapshotSubscription) {
            if (isFunction(state.snapshotSubscription.abort)) {
                state.snapshotSubscription.abort();
            } else if (isFunction(state.snapshotSubscription.unsubscribe)) {
                state.snapshotSubscription.unsubscribe();
            }
        }
        cancelPendingSharedSync(state, (timerId: number): void => {
            this.lifecycleResources.clearTimer(timerId);
        });
        resetMutableStateAfterDestroy(state);
        state.api = this.#api;
    }
    private readonly publishMetric = (metric: string, value: number, tags: TelemetryFields): void => {
        this.dependencies.telemetry.publishMetric(metric, value, tags);
    };
    override async onDestroy(): Promise<void> {
        this.#states.forEach((state) => {
            this.teardownConnection(state);
            this.destroySourceState(state);
            if (state.snapshotMeta.source === DEFAULT_LOG_SOURCE) {
                this.syncSharedBuffer(state, true);
            }
        });
        this.#states.clear();
        if (isFunction(this.#stateSubscription)) {
            this.#stateSubscription();
            this.#stateSubscription = null;
        }
    }
}
export { LogStream, LOG_STREAM_SERVICE_ID, type ConnectionEvent, type ConnectionStatus };
