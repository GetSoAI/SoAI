/* SoAI - Shared subscription manager service [frontend/assets/ts/core/subscriptionmanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { createSubscriptionManagerState, type SubscriptionManagerState } from '@core/subscriptionmanager/state.ts';
import { type ResourceSubscriptionHandler, type StreamManagerInterface, type SubscriptionHealth, type SubscriptionManagerDependencies, type SubscriptionHandler, type UnsubscribeEntry, type UnsubscribeFunction, type HealthStatus } from '@core/subscriptionmanager/contracts.ts';
import { log, type LogLevel, validateStreamManager } from '@core/subscriptionmanager/internalContracts.ts';
import { delay, ensureResourceStarted, ensureTimers, getStreamManagerForSubscription, resolveStreamManager, resolveUnsubscribeManager } from '@core/subscriptionmanager/effects.ts';
import { normalizeUnsubscribe } from '@core/subscriptionmanager/subscriptionExecution.ts';
import { createWrappedStateHandler, createWrappedValueHandler, ensureManagerReady, subscribeToResource, verifyManagerReadiness, getHealthStatus, destroyManager, type ResourceSubscriptionFactory } from '@core/subscriptionmanager/actions.ts';

interface EnsureReadyOptions {
    signal?: AbortSignal;
}

interface SubscriptionManagerFactory {
    create(ownerId: string, dependencies?: SubscriptionManagerDependencies): SubscriptionManager;
}

class SubscriptionManager {
    ownerId: string;
    #state: SubscriptionManagerState;
    #subscriptionVersion: number;
    readonly #requireActive: () => void;

    constructor(ownerId: string, dependencies: SubscriptionManagerDependencies = {}) {
        this.ownerId = ownerId;
        this.#state = createSubscriptionManagerState();
        this.#subscriptionVersion = 0;
        this.#requireActive = dependencies.requireActive ?? (() => {});
        this.#state.streamManager = dependencies.streamManager ? validateStreamManager(dependencies.streamManager) : null;
    }

    subscribeResourceState(key: string, handler: ResourceSubscriptionHandler): UnsubscribeFunction {
        return this.#subscribe(key, (manager, health, capturedVersion): UnsubscribeEntry => {
            return manager.subscriptions.subscribeResourceState(
                key,
                createWrappedStateHandler(health, capturedVersion, handler, () => this.#state.health.get(key) === health && this.#canDeliver()),
                { immediate: true }
            );
        });
    }

    subscribeResourceValue(key: string, handler: SubscriptionHandler): UnsubscribeFunction {
        return this.#subscribe(key, (manager, health, capturedVersion): UnsubscribeEntry => {
            return manager.subscriptions.subscribeResourceValue(
                key,
                createWrappedValueHandler(health, capturedVersion, handler, () => this.#state.health.get(key) === health && this.#canDeliver()),
                { immediate: true }
            );
        });
    }

    #subscribe(key: string, subscribe: ResourceSubscriptionFactory): UnsubscribeFunction {
        this.#requireActive();
        return subscribeToResource(
            {
                clearExisting: (subscriptionKey: string): void => {
                    this.unsubscribeResource(subscriptionKey);
                },
                isCurrent: (subscriptionKey, health) => this.#state.health.get(subscriptionKey) === health,
                incrementVersion: (): number => {
                    this.#subscriptionVersion += 1;
                    return this.#subscriptionVersion;
                },
                addHealth: (subscriptionKey: string, health: SubscriptionHealth): void => {
                    this.#state.health.set(subscriptionKey, health);
                },
                resolveStreamManager: (): StreamManagerInterface => resolveStreamManager(this.#state),
                setStreamManager: (streamManager: StreamManagerInterface): void => {
                    this.#state.streamManager = streamManager;
                },
                ensureTimers: (): void => ensureTimers(this.#state),
                putSubscription: (subscriptionKey: string, unsubscribe: UnsubscribeEntry, health: SubscriptionHealth): boolean => {
                    if (this.#state.health.get(subscriptionKey) !== health) {
                        this.#finalizeSubscription(unsubscribe);
                        return false;
                    }
                    try {
                        this.#requireActive();
                    } catch (error) {
                        this.#finalizeSubscription(unsubscribe);
                        throw error;
                    }
                    this.#state.subscriptions.set(subscriptionKey, unsubscribe);
                    return true;
                },
                beginResourceStart: (subscriptionKey: string, health: SubscriptionHealth): Promise<void> => {
                    return this.#ensureResourceStarted(subscriptionKey, health);
                },
                logDebug: (message: string, error?: Error): void => {
                    this.#log('debug', message, error);
                }
            },
            key,
            subscribe
        );
    }

    unsubscribeResource(key: string): void {
        const unsubscribe = this.#state.subscriptions.get(key);
        const pendingStart = this.#state.pendingStarts.get(key);
        this.#state.subscriptions.delete(key);
        this.#state.health.delete(key);
        this.#state.pendingStarts.delete(key);
        const failures: Error[] = [];
        if (pendingStart) runCleanupStepCollectingFailure(() => pendingStart.controller.abort(), failures);
        if (unsubscribe) runCleanupStepCollectingFailure(() => this.#finalizeSubscription(unsubscribe), failures);
        throwCollectedCleanupFailures(failures);
    }

    subscribeWebSocket(eventType: string, handler: (data: JsonValue) => void): UnsubscribeFunction {
        this.#requireActive();
        if (!eventType || typeof handler !== 'function') {
            throw new Error(`Invalid WebSocket subscription: ${eventType}`);
        }
        this.unsubscribeWebSocket(eventType);
        const wsClient = getWebSocketClient();
        let acquired: UnsubscribeFunction | null = null;
        let disposed = false;
        const release = (): void => {
            if (disposed) return;
            disposed = true;
            if (this.#state.wsSubscriptions.get(eventType) === release) this.#state.wsSubscriptions.delete(eventType);
            const unsubscribe = acquired;
            acquired = null;
            unsubscribe?.();
        };
        this.#state.wsSubscriptions.set(eventType, release);
        try {
            const unsubscribe = wsClient.subscribe(eventType, (payload) => {
                if (!disposed && this.#state.wsSubscriptions.get(eventType) === release && this.#canDeliver()) handler(payload);
            });
            if (disposed || this.#state.wsSubscriptions.get(eventType) !== release) {
                unsubscribe();
                return release;
            }
            acquired = unsubscribe;
            this.#requireActive();
        } catch (error) {
            release();
            throw error;
        }
        return release;
    }

    unsubscribeWebSocket(eventType: string): void {
        const unsubscribe = this.#state.wsSubscriptions.get(eventType);
        this.#state.wsSubscriptions.delete(eventType);
        if (isFunction(unsubscribe)) {
            unsubscribe();
        }
    }

    async ensureReady(options: EnsureReadyOptions = {}): Promise<void> {
        this.#requireActive();
        await ensureManagerReady(
            {
                getHealth: (): Map<string, SubscriptionHealth> => {
                    return this.#state.health;
                },
                getSubscriptions: (): Map<string, UnsubscribeEntry> => {
                    return this.#state.subscriptions;
                },
                resolveStreamManager: (): Promise<StreamManagerInterface> => {
                    return getStreamManagerForSubscription(this.#state);
                },
                ensureResourceStarted: (key: string, health: SubscriptionHealth, options?: { signal?: AbortSignal | undefined }): Promise<void> => {
                    return this.#ensureResourceStarted(key, health, options);
                },
                delay: (ms: number): Promise<void> => {
                    return delay(this.#state, ms);
                },
                logDebug: (_message: string, error?: Error): void => {
                    this.#log('debug', _message, error);
                }
            },
            options
        );
    }

    async verifyReady(): Promise<void> {
        await verifyManagerReadiness({
            getHealth: (): Map<string, SubscriptionHealth> => {
                return this.#state.health;
            },
            resolveStreamManager: (): Promise<StreamManagerInterface> => {
                return getStreamManagerForSubscription(this.#state);
            },
            delay: (ms: number): Promise<void> => {
                return delay(this.#state, ms);
            },
            logDebug: (_message: string, error?: Error): void => {
                this.#log('debug', _message, error);
            }
        });
    }

    getHealthStatus(): HealthStatus[] {
        return getHealthStatus(this.#state.health);
    }

    destroy(): void {
        destroyManager({
            subscriptions: this.#state.subscriptions,
            health: this.#state.health,
            wsSubscriptions: this.#state.wsSubscriptions,
            pendingStarts: this.#state.pendingStarts,
            timers: this.#state.timers,
            clearTimers: (): void => {
                this.#state.timers = null;
            },
            finalizeSubscription: (entry: UnsubscribeEntry | undefined): void => {
                this.#finalizeSubscription(entry);
            },
            finalizeWebSocket: (unsubscribe: UnsubscribeFunction | undefined): void => {
                if (isFunction(unsubscribe)) {
                    unsubscribe();
                }
            },
            clearStreamManager: (): void => {
                this.#state.streamManager = null;
            }
        });
        this.#subscriptionVersion = 0;
    }

    #log(level: LogLevel, message: string, error?: Error): void {
        log(level, this.ownerId, message, error);
    }

    #canDeliver(): boolean {
        try {
            this.#requireActive();
            return true;
        } catch (error) {
            if (isAbortError(error)) return false;
            throw ensureError(error);
        }
    }

    #finalizeSubscription(entry: UnsubscribeEntry | undefined): void {
        normalizeUnsubscribe(resolveUnsubscribeManager(this.#state), entry)();
    }

    #ensureResourceStarted(key: string, health: SubscriptionHealth, options: { signal?: AbortSignal | undefined } = {}): Promise<void> {
        this.#requireActive();
        return ensureResourceStarted(
            this.#state,
            key,
            health,
            (entryKey: string, entryHealth: SubscriptionHealth, error: Error) => {
                this.#recordError(entryKey, entryHealth, error);
            },
            options
        );
    }

    #recordError(key: string, health: SubscriptionHealth, error: Error): void {
        health.errors += 1;
        health.readyChecked = true;
        this.#log('debug', `Subscription readiness failed for ${key}`, error);
    }
}

const subscriptionManager: SubscriptionManagerFactory = Object.freeze({
    create(ownerId: string, dependencies: SubscriptionManagerDependencies = {}): SubscriptionManager {
        return new SubscriptionManager(ownerId, dependencies);
    }
});

export { SubscriptionManager, subscriptionManager };
export type { SubscriptionManagerFactory, SubscriptionManagerDependencies, SubscriptionHandler, UnsubscribeEntry, UnsubscribeFunction, HealthStatus, StreamManagerInterface };
