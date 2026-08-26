/* SoAI - Stream resource and bundle subscription ownership [frontend/assets/ts/core/realtime/streammanager/streamSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import type { StreamResourceStore } from '@core/realtime/streammanager/resourceStore.ts';
import type { StreamTransport } from '@core/realtime/streammanager/streamTransport.ts';
import type { BundleDefinition, BundleHandlers, ResourceListener, ResourceSubscriptionOptions } from '@core/realtime/streammanager/types.ts';
import type { ResourceStateListener, ResourceValueListener } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { bindResourceTypedSubscription, createResourceTypedSubscription, removeResourceTypedSubscription } from '@core/realtime/streammanager/resources/resourceTypedSubscriptions.ts';
import { hasResourceLiveDemand } from '@core/realtime/streammanager/resources/resourceActivationPolicy.ts';
import { isFunction } from '@core/typeGuards.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';

class StreamSubscriptions {
    readonly #store: StreamResourceStore;
    readonly #resources: StreamResourceLoader;
    readonly #transport: StreamTransport;
    readonly #disposers = new Set<() => void>();
    readonly #bundleAborts = new Set<() => void>();
    #disposed = false;

    constructor(store: StreamResourceStore, resources: StreamResourceLoader, transport: StreamTransport) {
        this.#store = store;
        this.#resources = resources;
        this.#transport = transport;
    }

    subscribeResourceState(name: string, listener: ResourceStateListener, options: ResourceSubscriptionOptions = {}): () => void {
        this.#requireActive();
        const key = toTrimmedString(name);
        if (!key) throw new Error('Stream resource state subscription requires a resource key');
        if (!isFunction(listener)) throw new Error('Stream resource state subscription requires a handler');
        const resource = this.#store.get(key);
        if (!resource) throw new Error(`Stream resource state subscription requires a registered resource: ${key}`);
        const interestToken = this.#transport.acquireInterest(key);
        const typedSubscriber = createResourceTypedSubscription(resource, listener);
        resource.reconciler.setLiveDemand(hasResourceLiveDemand(resource));
        const unsubscribe = (): void => {
            removeResourceTypedSubscription(resource, typedSubscriber);
            resource.reconciler.setLiveDemand(hasResourceLiveDemand(resource));
            this.#transport.releaseInterest(interestToken);
        };
        const dispose = this.#own(unsubscribe);
        try {
            typedSubscriber.initial = options.immediate !== false;
            bindResourceTypedSubscription(resource, typedSubscriber, options.immediate !== false);
        } catch (error) {
            dispose();
            throw error;
        }
        if (typedSubscriber.active && resource.status === 'unavailable' && this.#resources.ready && (resource.config.autoStart || options.ensureStart !== false)) {
            this.#resources.startOwned(key, 'Subscribed resource start');
        }
        return dispose;
    }

    subscribeResourceValue(name: string, listener: ResourceValueListener, options: ResourceSubscriptionOptions = {}): () => void {
        if (!isFunction(listener)) throw new Error('Stream resource value subscription requires a handler');
        return this.subscribeResourceState(
            name,
            (snapshot, context): void => {
                if (snapshot.status !== 'ready') return;
                listener(snapshot.value, context ?? { type: snapshot.transitionType, transitionType: snapshot.transitionType, initial: false });
            },
            options
        );
    }

    #subscribeBundleResource(name: string, listener: ResourceListener, options: ResourceSubscriptionOptions & { signal?: AbortSignal | null }): () => void {
        return this.#store.subscribe(name, listener, options, {
            ready: this.#resources.ready,
            acquireInterest: (resourceName) => this.#transport.acquireInterest(resourceName),
            releaseInterest: (token) => this.#transport.releaseInterest(token),
            startOwned: (resourceName) => this.#resources.startOwned(resourceName, 'Subscribed resource start')
        });
    }

    #own(unsubscribe: () => void): () => void {
        let active = true;
        const dispose = (): void => {
            if (!active) return;
            active = false;
            this.#disposers.delete(dispose);
            unsubscribe();
        };
        this.#disposers.add(dispose);
        return dispose;
    }

    createBundle(definition: BundleDefinition, handlers: BundleHandlers = {}, options: { signal?: AbortSignal | null } = {}): ReturnType<StreamResourceStore['createBundleSubscription']> {
        this.#requireActive();
        if (!definition) throw new Error('Bundle required');
        const subscription = this.#store.createBundleSubscription(
            definition,
            handlers,
            options.signal ?? null,
            async (bundle) => {
                await this.#resources.ensureBundleResources(bundle);
            },
            (name, listener, subscriptionOptions) => this.#own(this.#subscribeBundleResource(name, listener, subscriptionOptions))
        );
        const abort = (): void => {
            this.#bundleAborts.delete(abort);
            subscription.abort();
        };
        if (!subscription.controller.signal.aborted) {
            this.#bundleAborts.add(abort);
            const releaseOwnership = (): void => {
                this.#bundleAborts.delete(abort);
            };
            subscription.controller.signal.addEventListener('abort', releaseOwnership, { once: true });
        }
        return { ...subscription, abort };
    }

    subscribeBundle(name: string, handlers: BundleHandlers = {}, options: { signal?: AbortSignal | null } = {}): ReturnType<StreamResourceStore['createBundleSubscription']> {
        this.#requireActive();
        const definition = this.#store.getBundle(name);
        if (!definition) throw new Error(`Unknown bundle: ${name}`);
        return this.createBundle(definition, handlers, options);
    }

    unsubscribe(target: (() => void) | { unsubscribe?: () => void; close?: () => void } | string | null | undefined): void {
        this.#store.unsubscribe(target);
    }

    unsubscribeAll(): void {
        this.#requireActive();
        this.#releaseAll();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#releaseAll();
    }

    #releaseAll(): void {
        for (const abort of [...this.#bundleAborts]) {
            abort();
        }
        for (const dispose of [...this.#disposers]) {
            dispose();
        }
    }

    #requireActive(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Stream subscriptions are disposed', 'stream-subscriptions-disposed');
    }
}

export { StreamSubscriptions };
