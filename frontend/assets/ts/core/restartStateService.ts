/* SoAI - Shared frontend restart state service [frontend/assets/ts/core/restartStateService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import { createEmptyRestartState, extractCanonicalState, fetchRestartState, type RestartState } from '@core/restartStateGateway.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject, isString, hasOwn } from '@core/typeGuards.ts';

const STREAM_ID = STATUS;
const log = createModuleLogger('RestartStateService', { defaultLevel: 'debug' });

type StateListener = (state: RestartState) => void;

interface SubscribeOptions {
    immediate?: boolean;
}

interface SnapshotContext {
    type?: string;
    lifecycle?: string;
}

class RestartStateService extends LifecycleModel {
    subscribers: Set<StateListener>;
    state: RestartState;
    lastSignature: string;
    unsubscribeStream: (() => void) | null;
    streamTask: Promise<void> | null;
    bootstrapTask: Promise<RestartState | undefined> | null;
    retryTimer: number | null;
    #snapshotGeneration = 0;
    #streamGeneration = 0;
    #lastResourceSnapshot: ResourceReconciliationSnapshot | null = null;
    #transitionLifecycle: string | null = null;

    constructor() {
        super({ name: 'core.restartStateService', type: 'service', moduleId: 'core.restartStateService' });
        this.subscribers = new Set();
        this.state = createEmptyRestartState();
        this.lastSignature = JSON.stringify(this.state);
        this.unsubscribeStream = null;
        this.streamTask = null;
        this.bootstrapTask = null;
        this.retryTimer = null;
    }

    override getRequiredResources(): string[] {
        return [STREAM_ID];
    }

    triggerBootstrap(reason: string = 'unspecified'): Promise<RestartState | undefined> | null {
        if (this.bootstrapTask) {
            return this.bootstrapTask;
        }
        const snapshotGeneration = this.#snapshotGeneration;
        this.bootstrapTask = (async () => {
            try {
                const state = await fetchRestartState();
                if (snapshotGeneration === this.#snapshotGeneration) {
                    this.applyState(this.#acceptConnectionTransition(state, null));
                }
                return state;
            } catch (error) {
                const runtimeError = ensureError(error);
                if (!isLifecycleCancellationError(runtimeError)) {
                    errorHandler.error('RestartStateService', 'Restart state bootstrap fetch failed', {
                        error: runtimeError,
                        reason
                    });
                }
                return undefined;
            } finally {
                this.bootstrapTask = null;
            }
        })();
        return this.bootstrapTask;
    }

    subscribe(listener: StateListener, options: SubscribeOptions = {}): () => void {
        if (!isFunction(listener)) {
            throw new Error('Restart state subscriber must be a function');
        }
        const { immediate = true } = options;
        this.subscribers.add(listener);
        if (immediate) {
            this.safeNotify(listener, this.state);
        }
        this.ensureActive();
        return () => {
            this.subscribers.delete(listener);
            if (this.subscribers.size === 0) {
                this.stopStream();
                if (this.retryTimer !== null) {
                    this.lifecycleResources.clearTimer(this.retryTimer);
                    this.retryTimer = null;
                }
            }
        };
    }

    getState(): RestartState {
        return this.state;
    }

    ensureActive(): void {
        if (this.retryTimer !== null && this.subscribers.size === 0) {
            this.lifecycleResources.clearTimer(this.retryTimer);
            this.retryTimer = null;
        }
        if (!this.streamTask && this.unsubscribeStream === null) {
            this.streamTask = (async () => {
                try {
                    await this.startStream();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (!isLifecycleCancellationError(runtimeError)) {
                        errorHandler.error('RestartStateService', 'Restart state stream failed to start', runtimeError);
                    }
                    this.stopStream();
                    this.scheduleRetry();
                } finally {
                    this.streamTask = null;
                    if (this.subscribers.size > 0 && this.unsubscribeStream === null) this.scheduleRetry();
                }
            })();
        }
        this.triggerBootstrap('ensure-active');
    }

    scheduleRetry(): void {
        if (this.retryTimer !== null) {
            return;
        }
        if (this.subscribers.size === 0) {
            return;
        }
        this.retryTimer = this.lifecycleResources.setTimer(() => {
            this.retryTimer = null;
            this.ensureActive();
        }, 2500);
    }

    async startStream(): Promise<void> {
        const streamGeneration = this.#streamGeneration;
        const manager = await this.ensureStreamResources([STREAM_ID], {
            allowDiscovery: true,
            strict: true
        });
        if (streamGeneration !== this.#streamGeneration || this.subscribers.size === 0) return;
        const unsubscribe = manager.subscriptions.subscribeResourceState(STREAM_ID, (snapshot: ResourceReconciliationSnapshot) => this.handleResourceSnapshot(snapshot), { immediate: true });
        if (streamGeneration !== this.#streamGeneration || this.subscribers.size === 0) {
            if (isFunction(unsubscribe)) unsubscribe();
            return;
        }
        this.unsubscribeStream = () => {
            if (isFunction(unsubscribe)) {
                unsubscribe();
            }
            this.unsubscribeStream = null;
        };
    }

    stopStream(): void {
        this.#streamGeneration += 1;
        this.#snapshotGeneration += 1;
        if (this.unsubscribeStream) {
            this.unsubscribeStream();
        }
        if (this.retryTimer !== null) {
            this.lifecycleResources.clearTimer(this.retryTimer);
            this.retryTimer = null;
        }
    }

    handleSnapshot(snapshot: JsonValue | null | undefined, context: SnapshotContext | null = null): void {
        const snapshotContext: SnapshotContext = isObject(context) ? context : {};
        const eventType = isString(snapshotContext.type) ? snapshotContext.type.toLowerCase() : '';
        const payload = isObject(snapshot) && hasOwn(snapshot, 'value') ? snapshot['value'] : snapshot;
        if (!payload || !isObject(payload)) {
            if (eventType === 'immediate' || eventType === 'initial') {
                this.triggerBootstrap(`recover-${eventType || 'unknown'}`);
            }
            return;
        }
        if (!hasOwn(payload, 'systemState')) {
            if (eventType === 'immediate' || eventType === 'initial') {
                this.triggerBootstrap(`recover-${eventType || 'unknown'}`);
            }
            return;
        }
        let canonical: RestartState;
        try {
            canonical = extractCanonicalState(payload);
        } catch (error) {
            const runtimeError = ensureError(error);
            log('error', 'Restart state snapshot is invalid', { error: runtimeError, payload, eventType });
            this.triggerBootstrap(`recover-${eventType || 'error'}`);
            throw runtimeError;
        }
        this.applyState(this.#acceptConnectionTransition(canonical, snapshotContext.lifecycle ?? null));
    }

    handleResourceSnapshot(snapshot: ResourceReconciliationSnapshot): void {
        if (snapshot.status !== 'ready' || snapshot.retained) return;
        const previous = this.#lastResourceSnapshot;
        if (previous !== null && snapshot.lifecycleGeneration < previous.lifecycleGeneration) return;
        if (previous !== null && snapshot.lifecycleGeneration === previous.lifecycleGeneration) {
            if (snapshot.transportEpoch < previous.transportEpoch) return;
            if (snapshot.transportEpoch === previous.transportEpoch && (snapshot.revision < previous.revision || snapshot.committedReconciliationRevision < previous.committedReconciliationRevision || snapshot.receiveSequence < previous.receiveSequence)) return;
        }
        this.#lastResourceSnapshot = snapshot;
        this.#snapshotGeneration += 1;
        this.handleSnapshot(snapshot.value, { type: snapshot.transitionType, lifecycle: `${String(snapshot.lifecycleGeneration)}:${String(snapshot.transportEpoch)}` });
    }

    #acceptConnectionTransition(state: RestartState, lifecycle: string | null): RestartState {
        const current = this.state.connectionTransition;
        const incoming = state.connectionTransition;
        const sameLifecycle = lifecycle === null || lifecycle === this.#transitionLifecycle;
        if (lifecycle !== null) this.#transitionLifecycle = lifecycle;
        if (!sameLifecycle || current === null) return state;
        const outdated = incoming === null || (incoming.instanceId === current.instanceId && incoming.configurationRevision < current.configurationRevision);
        return outdated ? { ...state, connectionTransition: current } : state;
    }

    applyState(state: RestartState): void {
        const signature = JSON.stringify(state);
        if (signature === this.lastSignature) {
            return;
        }
        this.state = state;
        this.lastSignature = signature;
        this.notifySubscribers(state);
    }

    dismissReminder(): void {
        this.#snapshotGeneration += 1;
        this.applyState({ ...createEmptyRestartState(), connectionTransition: this.state.connectionTransition });
    }

    resetState(): void {
        this.#snapshotGeneration += 1;
        this.#lastResourceSnapshot = null;
        this.#transitionLifecycle = null;
        this.applyState(createEmptyRestartState());
    }

    notifySubscribers(state: RestartState): void {
        this.subscribers.forEach((listener) => this.safeNotify(listener, state));
    }

    safeNotify(listener: StateListener, state: RestartState): void {
        try {
            listener(state);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('RestartStateService', 'Restart state listener failed', runtimeError);
        }
    }
}

let restartStateServiceInstance: RestartStateService | null = null;

const getRestartStateService = (): RestartStateService => {
    if (!restartStateServiceInstance) {
        restartStateServiceInstance = new RestartStateService();
    }
    return restartStateServiceInstance;
};

const resetRestartStateService = (): void => {
    if (!restartStateServiceInstance) {
        return;
    }
    restartStateServiceInstance.resetState();
    restartStateServiceInstance.stopStream();
    restartStateServiceInstance.subscribers.clear();
    restartStateServiceInstance = null;
};

const triggerRestartStateBootstrap = (reason: string): Promise<RestartState | undefined> | null => getRestartStateService().triggerBootstrap(reason);

const getRestartState = (): RestartState => getRestartStateService().getState();

const dismissRestartReminder = (): void => {
    getRestartStateService().dismissReminder();
};

const subscribeRestartState = (listener: StateListener, options: SubscribeOptions = {}): (() => void) => getRestartStateService().subscribe(listener, options);

export { RestartStateService, getRestartState, getRestartStateService, dismissRestartReminder, resetRestartStateService, subscribeRestartState, triggerRestartStateBootstrap };
