/* SoAI - Bootstrap-owned normalized collection data hub [frontend/assets/ts/core/data/ClientDataHub.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { CollectionResourceChannel } from '@core/data/clientdatahub/service.ts';
import type { ClientDataHubDependencies, ClientDataHubSubscribeOptions, CollectionChannelDefinition, OptimisticOperation, OptimisticStatus, ResourceDiff, ResourceIncomingObject, ResourceIncomingValue, ResourceItem, ResourceListener, ResourceMeta, ResourceOperation, ResourceSnapshot } from '@core/data/clientdatahub/types.ts';
import { normalizeResourceKey } from '@core/data/clientdatahub/guards.ts';
import { isFunction } from '@core/typeGuards.ts';

class ClientDataHub {
    #disposed = false;
    readonly #channels = new Map<string, CollectionResourceChannel>();
    readonly #dependencies: Pick<ClientDataHubDependencies, 'ensureResourceReady' | 'refreshResource'>;

    constructor(dependencies: ClientDataHubDependencies) {
        this.#dependencies = dependencies;
        for (const definition of dependencies.definitions) {
            const resource = normalizeResourceKey(definition.resource);
            if (this.#channels.has(resource)) throw new Error(`Duplicate collection channel: ${resource}`);
            this.#channels.set(resource, new CollectionResourceChannel(Object.freeze({ ...definition, resource }), dependencies));
        }
    }

    subscribe(resource: string, listener: ResourceListener, options: ClientDataHubSubscribeOptions = {}): () => void {
        this.#requireActive();
        if (!isFunction(listener)) throw new TypeError('ClientDataHub.subscribe requires a listener');
        return this.#channel(resource).addListener(listener, options.emitInitial !== false);
    }

    snapshot(resource: string): ResourceSnapshot {
        return this.#channel(resource).snapshot;
    }

    applyLocalOperation(resource: string, operation: ResourceOperation): ResourceSnapshot {
        this.#requireActive();
        return this.#channel(resource).applyLocalOperation(operation);
    }

    beginOptimisticOperation(resource: string, operation: OptimisticOperation): ResourceSnapshot {
        this.#requireActive();
        return this.#channel(resource).beginOptimisticOperation(operation);
    }

    markOptimisticOperationTerminal(resource: string, operationId: string, status: OptimisticStatus): ResourceSnapshot {
        this.#requireActive();
        return this.#channel(resource).markOptimisticOperationTerminal(operationId, status);
    }

    hasPendingOptimisticOperation(resource: string, itemId: string): boolean {
        return this.#channel(resource).hasPendingOptimisticOperation(itemId);
    }

    async ensureResource(resource: string, force = false): Promise<ResourceSnapshot> {
        this.#requireActive();
        const channel = this.#channel(resource);
        if (force) await this.#dependencies.refreshResource(resource);
        else await this.#dependencies.ensureResourceReady(resource);
        this.#requireActive();
        return channel.snapshot;
    }

    dispose(): void {
        this.#disposed = true;
        const failures: Error[] = [];
        for (const channel of this.#channels.values()) runCleanupStepCollectingFailure(() => channel.dispose(), failures);
        throwCollectedCleanupFailures(failures);
    }

    #requireActive(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Client data hub is disposed', 'client-data-hub-disposed');
    }

    #channel(resource: string): CollectionResourceChannel {
        const key = normalizeResourceKey(resource);
        const channel = this.#channels.get(key);
        if (!channel) throw new Error(`Unregistered collection channel: ${key}`);
        return channel;
    }
}

export { ClientDataHub };
export type { ClientDataHubDependencies, ClientDataHubSubscribeOptions, CollectionChannelDefinition, ResourceDiff, ResourceIncomingObject, ResourceIncomingValue, ResourceItem, ResourceListener, ResourceMeta, ResourceOperation, ResourceSnapshot };
