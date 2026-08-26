/* SoAI - Frontend realtime service ownership [frontend/assets/ts/core/realtime/RealtimeService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createController } from '@core/realtime/actions.ts';
import { HARDWARE_CAPABILITIES_RESOURCES, MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { deleteOwnerState, ensureManager, ensureOwnerState, ensureResourceStarted, getOwnerState, normalizeIdentifier, selectStreamManager, type RealtimeIdentifier } from '@core/realtime/state.ts';
import { isObject, isThenable } from '@core/typeGuards.ts';
import { getStreamResources } from '@core/realtime/streammanager/public.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

import type { StreamManagerInterface, SubscriptionController, SubscriptionHandlers, SubscriptionOptions } from '@core/realtime/types.ts';

const REALTIME_SERVICE_ID = 'core.realtime';

class RealtimeService {
    initialized: boolean;

    constructor() {
        this.initialized = false;
    }

    ensureAutoResources(options: { signal?: AbortSignal | undefined } = {}): Promise<void> {
        const result = getStreamResources().startAuto(options);
        if (!isThenable(result)) {
            return Promise.resolve();
        }
        return Promise.resolve(result).then(() => undefined);
    }

    fetchModels(): Promise<void> {
        return ensureResourceStarted(MODELS);
    }

    fetchPlugins(): Promise<void> {
        return ensureResourceStarted(PLUGINS);
    }

    fetchHardwareCapabilities(): Promise<void[]> {
        return Promise.all(HARDWARE_CAPABILITIES_RESOURCES.map((name) => ensureResourceStarted(name)));
    }

    createManagedSubscription(owner: WeakKey, inputOptions: SubscriptionOptions = {}): SubscriptionController {
        if (!owner) {
            throw new TypeError('createManagedSubscription requires an owner');
        }

        const manager = selectStreamManager(inputOptions.streamManager);
        if (!manager) {
            if (typeof inputOptions.onUnavailable === 'function') {
                inputOptions.onUnavailable();
            }
            throw new Error('StreamManager unavailable');
        }

        const key = inputOptions.key || inputOptions.resource || inputOptions.endpoint;
        if (!key) {
            throw new Error('createManagedSubscription requires a key');
        }

        const state = ensureOwnerState(owner);
        const existing = state.subscriptions.get(key);
        if (existing) {
            existing.stop();
            state.subscriptions.delete(key);
        }

        if (!inputOptions.handlers || !isObject(inputOptions.handlers)) {
            throw new Error('subscribe requires inputOptions.handlers object');
        }

        const baseOptions: SubscriptionOptions = {
            ...inputOptions,
            handlers: { ...inputOptions.handlers }
        };

        const controller = createController(owner, manager, baseOptions);
        state.subscriptions.set(key, controller);
        return controller;
    }

    stop(owner: WeakKey, key: string | null = null): void {
        if (!owner) {
            return;
        }
        const state = getOwnerState(owner);
        if (!state) {
            return;
        }
        if (key) {
            const subscription = state.subscriptions.get(key);
            subscription?.stop();
            state.subscriptions.delete(key);
            return;
        }
        state.subscriptions.forEach((subscription) => subscription.stop());
        state.subscriptions.clear();
    }

    dispose(owner: WeakKey): void {
        if (!owner) {
            return;
        }
        const state = getOwnerState(owner);
        if (!state) {
            return;
        }
        state.subscriptions.forEach((subscription) => subscription.stop());
        state.subscriptions.clear();
        deleteOwnerState(owner);
    }

    unsubscribe(identifier: RealtimeIdentifier): void {
        const id = normalizeIdentifier(identifier);
        ensureManager().unsubscribe?.(id);
    }

    reset(): void {
        this.initialized = false;
    }
}

const createRealtimeService = (): RealtimeService => new RealtimeService();

const requireRealtimeService = (): RealtimeService => {
    const candidate = resolveKernelService(REALTIME_SERVICE_ID);
    if (!(candidate instanceof RealtimeService)) {
        throw new Error(`${REALTIME_SERVICE_ID} has not been registered`);
    }
    return candidate;
};

export { RealtimeService, createRealtimeService, requireRealtimeService };
export type { SubscriptionHandlers, SubscriptionOptions, SubscriptionController, StreamManagerInterface };
