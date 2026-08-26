/* SoAI - Copy-on-write normalized collection freshness store [frontend/assets/ts/core/data/clientdatahub/collectionResourceStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionResourceSnapshot, CollectionResourceStateInput, ImmutableResourceDiff, LocalCollectionOperation, OptimisticCollectionEntry, OptimisticCollectionOperation, OptimisticTerminalStatus } from '@core/data/clientdatahub/collectionResourceContracts.ts';
import { createEmptyDiff } from '@core/data/clientdatahub/actions.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';
import type { ResourceDiff, ResourceIncomingValue, ResourceItem } from '@core/data/clientdatahub/types.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { isArray, isPlainObject } from '@core/typeGuards.ts';

type TrackBy = (item: ResourceItem) => string | null;

const freezeIncomingValue = (value: ResourceIncomingValue): ResourceIncomingValue => {
    if (isArray(value)) return Object.freeze(value.map((entry) => freezeIncomingValue(entry)));
    if (!isPlainObject(value)) return value;
    const frozen: ResourceItem = {};
    for (const [key, entry] of Object.entries(value)) frozen[key] = freezeIncomingValue(entry);
    return Object.freeze(frozen);
};

const immutableItem = (item: ResourceItem, label: string): ResourceItem => {
    const normalized = normalizeResourceItem(item, label);
    for (const [key, value] of Object.entries(normalized)) normalized[key] = freezeIncomingValue(value);
    return Object.freeze(normalized);
};

const immutableDiff = (diff: ResourceDiff): ImmutableResourceDiff =>
    Object.freeze({
        added: Object.freeze(diff.added.slice()),
        updated: Object.freeze(diff.updated.slice()),
        removed: Object.freeze(diff.removed.slice())
    });

const matchesDesiredProjection = (authoritative: ResourceItem, desired: ResourceItem): boolean => {
    return Object.entries(desired).every(([key, value]) => deepEqual(authoritative[key], value));
};

class CollectionResourceStore {
    readonly #resource: string;
    readonly #trackBy: TrackBy;
    #authoritativeItems = new Map<string, ResourceItem>();
    #authoritativeOrder: string[] = [];
    #localItems = new Map<string, ResourceItem | null>();
    #optimisticEntries = new Map<string, OptimisticCollectionEntry>();
    #snapshot: CollectionResourceSnapshot;

    constructor(resource: string, trackBy: TrackBy) {
        this.#resource = resource.trim();
        if (!this.#resource) throw new Error('Collection resource store requires a resource identifier');
        this.#trackBy = trackBy;
        this.#snapshot = this.#createSnapshot({
            version: 0,
            items: Object.freeze([]),
            orderedIds: Object.freeze([]),
            diff: immutableDiff(createEmptyDiff()),
            status: 'initializing',
            availability: 'loading',
            hasAuthoritativeSnapshot: false,
            authoritativeRevision: 0,
            authoritativeUpdatedAtMonotonicMs: null,
            staleSinceMonotonicMs: null,
            authoritativeSource: null,
            authoritativeReason: null,
            retained: false,
            pendingOptimisticOperationIds: Object.freeze([])
        });
    }

    get snapshot(): CollectionResourceSnapshot {
        return this.#snapshot;
    }

    hasPendingOptimisticOperation(itemId: string): boolean {
        const normalizedItemId = itemId.trim();
        return normalizedItemId.length > 0 && [...this.#optimisticEntries.values()].some((entry) => entry.itemId === normalizedItemId);
    }

    applyResourceState(input: CollectionResourceStateInput): CollectionResourceSnapshot {
        if (!Number.isSafeInteger(input.revision) || input.revision < this.#snapshot.authoritativeRevision) return this.#snapshot;
        if (input.status === 'ready') {
            if (!Array.isArray(input.value)) throw new Error(`${this.#resource} ready state requires an array value`);
            this.#replaceAuthoritative(input.value, input.revision);
            this.#clearMatchingSuccessfulOptimism(input.revision);
            const reconcilingOptimism = this.#hasSuccessfulOptimism();
            return this.#publishProjection({
                status: reconcilingOptimism ? 'recovering' : 'ready',
                availability: reconcilingOptimism ? 'stale' : this.#authoritativeOrder.length === 0 ? 'ready-empty' : 'ready',
                hasAuthoritativeSnapshot: true,
                authoritativeRevision: input.revision,
                authoritativeUpdatedAtMonotonicMs: input.committedAtMonotonicMs,
                staleSinceMonotonicMs: reconcilingOptimism ? (this.#snapshot.staleSinceMonotonicMs ?? input.committedAtMonotonicMs) : null,
                authoritativeSource: input.source,
                authoritativeReason: input.reason,
                retained: reconcilingOptimism
            });
        }
        const hasAuthoritativeSnapshot = this.#snapshot.hasAuthoritativeSnapshot;
        const stale = hasAuthoritativeSnapshot;
        const unavailable = input.status === 'unavailable' || input.status === 'disconnected' || input.status === 'error';
        this.#snapshot = this.#createSnapshot({
            ...this.#snapshot,
            version: this.#snapshot.version + 1,
            diff: immutableDiff(createEmptyDiff()),
            status: input.status,
            availability: stale ? 'stale' : unavailable ? 'unavailable' : 'loading',
            authoritativeReason: input.reason,
            staleSinceMonotonicMs: stale ? (this.#snapshot.staleSinceMonotonicMs ?? input.committedAtMonotonicMs) : null,
            retained: stale,
            pendingOptimisticOperationIds: this.#pendingOperationIds()
        });
        return this.#snapshot;
    }

    applyLocalOperation(operation: LocalCollectionOperation): CollectionResourceSnapshot {
        if (operation.type === 'upsert' && operation.item) {
            const item = immutableItem(operation.item, `${this.#resource} local item`);
            const itemId = this.#requireItemId(item);
            this.#localItems.set(itemId, item);
        } else if (operation.type === 'remove' && operation.id !== undefined) {
            this.#localItems.set(String(operation.id), null);
        } else if (operation.type === 'replace') {
            this.#localItems.clear();
            for (const entry of operation.items ?? []) {
                const item = immutableItem(entry, `${this.#resource} local replacement`);
                this.#localItems.set(this.#requireItemId(item), item);
            }
            for (const itemId of this.#authoritativeOrder) {
                if (!this.#localItems.has(itemId)) this.#localItems.set(itemId, null);
            }
        } else {
            throw new Error(`${this.#resource} received an unsupported local collection operation`);
        }
        return this.#publishProjection({});
    }

    beginOptimisticOperation(operation: OptimisticCollectionOperation): CollectionResourceSnapshot {
        performance.mark(`soai-audit:store-begin:${operation.operationId}`);
        const operationId = operation.operationId.trim();
        const itemId = operation.itemId.trim();
        if (!operationId || !itemId || !operation.acceptedTaskId.trim()) throw new Error('Optimistic collection operation identity is invalid');
        for (const entry of this.#optimisticEntries.values()) {
            if (entry.itemId === itemId) throw new Error(`Conflicting optimistic operation for ${itemId}`);
        }
        this.#optimisticEntries.set(
            operationId,
            Object.freeze({
                ...operation,
                operationId,
                itemId,
                desiredItem: operation.desiredItem === null ? null : immutableItem(operation.desiredItem, `${this.#resource} optimistic item`),
                startingAuthoritativeRevision: this.#snapshot.authoritativeRevision,
                terminalStatus: 'pending'
            })
        );
        return this.#publishProjection({});
    }

    markOptimisticOperationTerminal(operationId: string, status: OptimisticTerminalStatus): CollectionResourceSnapshot {
        const entry = this.#optimisticEntries.get(operationId);
        if (!entry) throw new Error(`Unknown optimistic operation ${operationId}`);
        performance.mark(`soai-audit:store-terminal-${status}-${entry && this.#matchesAuthoritative(entry) ? 'matching' : 'diverged'}:${operationId}`);
        if (status === 'succeeded') {
            if (this.#matchesAuthoritative(entry)) {
                this.#optimisticEntries.delete(operationId);
                return this.#publishProjection({});
            }
            this.#optimisticEntries.set(operationId, Object.freeze({ ...entry, terminalStatus: 'succeeded' }));
            return this.#publishProjection({
                status: 'recovering',
                availability: this.#snapshot.hasAuthoritativeSnapshot ? 'stale' : 'loading',
                retained: this.#snapshot.hasAuthoritativeSnapshot,
                staleSinceMonotonicMs: this.#snapshot.staleSinceMonotonicMs ?? performance.now(),
                authoritativeReason: 'optimistic-success-reconciliation'
            });
        }
        this.#optimisticEntries.delete(operationId);
        return this.#publishProjection({
            status: 'recovering',
            availability: this.#snapshot.hasAuthoritativeSnapshot ? 'stale' : 'loading',
            retained: this.#snapshot.hasAuthoritativeSnapshot,
            staleSinceMonotonicMs: this.#snapshot.staleSinceMonotonicMs ?? performance.now(),
            authoritativeReason: status
        });
    }

    #replaceAuthoritative(items: readonly ResourceItem[], revision: number): void {
        const nextItems = new Map<string, ResourceItem>();
        const nextOrder: string[] = [];
        for (const entry of items) {
            const normalized = immutableItem(entry, `${this.#resource} authoritative item`);
            const itemId = this.#requireItemId(normalized);
            if (nextItems.has(itemId)) throw new Error(`${this.#resource} contains duplicate item ${itemId}`);
            const previous = this.#authoritativeItems.get(itemId);
            nextItems.set(itemId, previous && deepEqual(previous, normalized) ? previous : normalized);
            nextOrder.push(itemId);
        }
        this.#authoritativeItems = nextItems;
        this.#authoritativeOrder = nextOrder;
        if (revision > this.#snapshot.authoritativeRevision) this.#localItems.clear();
    }

    #clearMatchingSuccessfulOptimism(revision: number): void {
        for (const [operationId, entry] of this.#optimisticEntries.entries()) {
            if (entry.terminalStatus === 'succeeded' && revision > entry.startingAuthoritativeRevision && this.#matchesAuthoritative(entry)) {
                performance.mark(`soai-audit:store-authority-clear:${operationId}`);
                this.#optimisticEntries.delete(operationId);
            }
        }
    }

    #matchesAuthoritative(entry: OptimisticCollectionEntry): boolean {
        const authoritative = this.#authoritativeItems.get(entry.itemId);
        return entry.desiredItem === null ? authoritative === undefined : authoritative !== undefined && matchesDesiredProjection(authoritative, entry.desiredItem);
    }

    #hasSuccessfulOptimism(): boolean {
        return [...this.#optimisticEntries.values()].some((entry) => entry.terminalStatus === 'succeeded');
    }

    #projection(): { items: readonly ResourceItem[]; orderedIds: readonly string[] } {
        const itemsById = new Map(this.#authoritativeItems);
        const order = this.#authoritativeOrder.slice();
        for (const [itemId, item] of this.#localItems.entries()) {
            if (item === null) {
                itemsById.delete(itemId);
                const index = order.indexOf(itemId);
                if (index >= 0) order.splice(index, 1);
            } else {
                itemsById.set(itemId, item);
                if (!order.includes(itemId)) order.push(itemId);
            }
        }
        for (const entry of this.#optimisticEntries.values()) {
            if (entry.desiredItem === null) {
                itemsById.delete(entry.itemId);
                const index = order.indexOf(entry.itemId);
                if (index >= 0) order.splice(index, 1);
            } else {
                const authoritative = itemsById.get(entry.itemId);
                const projected = immutableItem({ ...(authoritative ?? {}), ...entry.desiredItem }, `${this.#resource} optimistic projection`);
                const previousIndex = this.#snapshot.orderedIds.indexOf(entry.itemId);
                const previous = previousIndex >= 0 ? this.#snapshot.items[previousIndex] : undefined;
                itemsById.set(entry.itemId, previous && deepEqual(previous, projected) ? previous : projected);
                if (!order.includes(entry.itemId)) order.push(entry.itemId);
            }
        }
        const filteredOrder = order.filter((itemId) => itemsById.has(itemId));
        const items = filteredOrder.map((itemId) => {
            const item = itemsById.get(itemId);
            if (!item) throw new Error(`${this.#resource} projection lost item ${itemId}`);
            return item;
        });
        return { items: Object.freeze(items), orderedIds: Object.freeze(filteredOrder) };
    }

    #publishProjection(changes: Partial<CollectionResourceSnapshot>): CollectionResourceSnapshot {
        const projection = this.#projection();
        const diff = this.#diff(this.#snapshot.orderedIds, this.#snapshot.items, projection.orderedIds, projection.items);
        this.#snapshot = this.#createSnapshot({
            ...this.#snapshot,
            ...changes,
            version: this.#snapshot.version + 1,
            items: projection.items,
            orderedIds: projection.orderedIds,
            diff: immutableDiff(diff),
            pendingOptimisticOperationIds: this.#pendingOperationIds()
        });
        return this.#snapshot;
    }

    #diff(previousIds: readonly string[], previousItems: readonly ResourceItem[], nextIds: readonly string[], nextItems: readonly ResourceItem[]): ResourceDiff {
        const diff = createEmptyDiff();
        const previous = new Map(previousIds.map((itemId, index) => [itemId, previousItems[index]]));
        const next = new Map(nextIds.map((itemId, index) => [itemId, nextItems[index]]));
        for (const [itemId, item] of next.entries()) {
            if (!previous.has(itemId)) diff.added.push(itemId);
            else if (previous.get(itemId) !== item) diff.updated.push(itemId);
        }
        for (const itemId of previous.keys()) if (!next.has(itemId)) diff.removed.push(itemId);
        return diff;
    }

    #pendingOperationIds(): readonly string[] {
        return Object.freeze([...this.#optimisticEntries.keys()]);
    }

    #requireItemId(item: ResourceItem): string {
        const itemId = this.#trackBy(item)?.trim() ?? '';
        if (!itemId) throw new Error(`${this.#resource} item identity is missing`);
        return itemId;
    }

    #createSnapshot(values: Omit<CollectionResourceSnapshot, 'resource'>): CollectionResourceSnapshot {
        return Object.freeze({ resource: this.#resource, ...values });
    }
}

export { CollectionResourceStore };
