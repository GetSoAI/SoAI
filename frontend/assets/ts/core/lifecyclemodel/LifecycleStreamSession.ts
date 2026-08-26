/* SoAI - Frontend lifecycle stream session ownership [frontend/assets/ts/core/lifecyclemodel/LifecycleStreamSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureLifecycleDeclaredResources, ensureLifecycleStreamResources } from '@core/lifecyclemodel/effects.ts';
import { getLifecycleStreamManager, peekLifecycleStreamManager, resetLifecycleStreamManagerCache, subscribeLifecycleResource } from '@core/lifecyclemodel/service.ts';
import type { EnsureStreamResourcesOptions, GetStreamManagerOptions, PeekStreamManagerOptions, ResourceSnapshot, StreamRuntimeOwners, SubscribeResourceOptions } from '@core/lifecyclemodel/types.ts';
import type { LifecycleResources } from '@core/lifecyclemodel/LifecycleResources.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';

class LifecycleStreamSession {
    #manager: StreamRuntimeOwners | null = null;
    #declaredResourcesPromise: Promise<StreamRuntimeOwners | null> | null = null;
    #resources: LifecycleResources;

    constructor(resources: LifecycleResources) {
        this.#resources = resources;
    }

    subscribeResourceState(resource: string, handler: (snapshot: ResourceSnapshot) => void, options: SubscribeResourceOptions = {}): () => void {
        return subscribeLifecycleResource(
            {
                setTimeout: (callback, delay, timeoutOptions) => this.#resources.setTimer(callback, delay, { ...timeoutOptions, repeat: false }),
                clearTimer: (timerId) => this.#resources.clearTimer(timerId),
                trackDisposable: (resourceValue, cleanup) => this.#resources.track(resourceValue, cleanup),
                untrackDisposable: (resourceValue) => this.#resources.untrack(resourceValue),
                peekStreamManager: (peekOptions) => this.peek(peekOptions),
                getStreamManager: async (streamOptions) => this.get(streamOptions)
            },
            resource,
            handler,
            options
        );
    }

    peek(options?: PeekStreamManagerOptions): StreamRuntimeOwners | null {
        return peekLifecycleStreamManager(this.#cache(), options);
    }

    async get(options?: GetStreamManagerOptions): Promise<StreamRuntimeOwners> {
        return getLifecycleStreamManager(this.#cache(), options);
    }

    reset(): void {
        resetLifecycleStreamManagerCache(this.#cache());
        this.#declaredResourcesPromise = null;
    }

    async ensureDeclaredResources(identifier: string, requiredResources: string[], options: EnsureStreamResourcesOptions = {}): Promise<StreamRuntimeOwners | null> {
        return ensureLifecycleDeclaredResources(
            {
                getLifecycleIdentifier: () => identifier,
                getRequiredResources: () => requiredResources,
                getDeclaredResourcesPromise: () => this.#declaredResourcesPromise,
                setDeclaredResourcesPromise: (promise) => {
                    this.#declaredResourcesPromise = promise;
                },
                clearDeclaredResourcesPromise: (promise) => {
                    if (this.#declaredResourcesPromise === promise) this.#declaredResourcesPromise = null;
                },
                ensureStreamResources: async (resourceNames, streamOptions) => this.ensureResources(resourceNames, streamOptions)
            },
            options
        );
    }

    async ensureResources(resourceNames: string | string[], options?: EnsureStreamResourcesOptions): Promise<StreamRuntimeOwners> {
        return ensureLifecycleStreamResources({ getStreamManager: async (streamOptions) => this.get(streamOptions) }, resourceNames, options);
    }

    #cache(): { getCachedStreamManager(): StreamRuntimeOwners | null; setCachedStreamManager(manager: StreamRuntimeOwners | null): void; resolveGlobalStreamManager(): StreamRuntimeOwners | null } {
        return {
            getCachedStreamManager: () => this.#manager,
            setCachedStreamManager: (manager) => {
                this.#manager = manager;
            },
            resolveGlobalStreamManager: () => getStreamRuntime()
        };
    }
}

export { LifecycleStreamSession };
