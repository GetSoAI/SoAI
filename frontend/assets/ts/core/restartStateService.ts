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
}

class RestartStateService extends LifecycleModel {
    subscribers: Set<StateListener>;
    state: RestartState;
    lastSignature: string;
    unsubscribeStream: (() => void) | null;
    streamTask: Promise<void> | null;
    bootstrapTask: Promise<RestartState | undefined> | null;
    retryTimer: number | null;

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
        this.bootstrapTask = (async () => {
            try {
                const state = await fetchRestartState();
                this.applyState(state);
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
        if (!this.streamTask) {
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
        const manager = await this.ensureStreamResources([STREAM_ID], {
            allowDiscovery: true,
            strict: true
        });
        const unsubscribe = manager.subscriptions.subscribeResourceState(STREAM_ID, (snapshot: ResourceReconciliationSnapshot) => this.handleResourceSnapshot(snapshot), { immediate: true });
        this.unsubscribeStream = () => {
            if (isFunction(unsubscribe)) {
                unsubscribe();
            }
            this.unsubscribeStream = null;
        };
    }

    stopStream(): void {
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
        this.applyState(canonical);
    }

    handleResourceSnapshot(snapshot: ResourceReconciliationSnapshot): void {
        if (snapshot.status !== 'ready') return;
        this.handleSnapshot(snapshot.value, { type: snapshot.transitionType });
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

    resetState(): void {
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

const resetRestartState = (): void => {
    getRestartStateService().resetState();
};

const subscribeRestartState = (listener: StateListener, options: SubscribeOptions = {}): (() => void) => getRestartStateService().subscribe(listener, options);

export { RestartStateService, getRestartState, getRestartStateService, resetRestartState, resetRestartStateService, subscribeRestartState, triggerRestartStateBootstrap };
