/* SoAI - Normalized collection resource state contracts [frontend/assets/ts/core/data/clientdatahub/collectionResourceContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type CollectionResourceStatus = 'initializing' | 'unavailable' | 'ready' | 'recovering' | 'disconnected' | 'error';
type CollectionAvailability = 'loading' | 'unavailable' | 'ready-empty' | 'ready' | 'stale';
type OptimisticTerminalStatus = 'succeeded' | 'failed' | 'cancelled';
type ResourcePrimitiveValue = string | number | bigint | boolean | null | undefined;
type ResourceIncomingValue = ResourcePrimitiveValue | ResourceIncomingObject | readonly ResourceIncomingValue[];

interface ResourceIncomingObject {
    [key: string]: ResourceIncomingValue;
}

interface ResourceItem extends ResourceIncomingObject {
    id?: string | number | null | undefined;
    name?: string | null | undefined;
}

interface CollectionResourceStateInput {
    status: CollectionResourceStatus;
    value: readonly ResourceItem[] | null;
    revision: number;
    committedAtMonotonicMs: number;
    source: string;
    reason: string;
}

interface CollectionResourceSnapshot {
    resource: string;
    version: number;
    items: readonly ResourceItem[];
    orderedIds: readonly string[];
    diff: ImmutableResourceDiff;
    status: CollectionResourceStatus;
    availability: CollectionAvailability;
    hasAuthoritativeSnapshot: boolean;
    authoritativeRevision: number;
    authoritativeUpdatedAtMonotonicMs: number | null;
    staleSinceMonotonicMs: number | null;
    authoritativeSource: string | null;
    authoritativeReason: string | null;
    retained: boolean;
    pendingOptimisticOperationIds: readonly string[];
}

interface ImmutableResourceDiff {
    added: readonly string[];
    updated: readonly string[];
    removed: readonly string[];
}

interface OptimisticCollectionOperation {
    operationId: string;
    itemId: string;
    desiredItem: ResourceItem | null;
    acceptedTaskId: string;
}

interface OptimisticCollectionEntry extends OptimisticCollectionOperation {
    startingAuthoritativeRevision: number;
    terminalStatus: 'pending' | 'succeeded';
}

interface LocalCollectionOperation {
    type: string;
    item?: ResourceItem | undefined;
    items?: ResourceItem[] | undefined;
    id?: string | number | undefined;
    ids?: (string | number)[] | undefined;
}

export type { CollectionAvailability, CollectionResourceSnapshot, CollectionResourceStateInput, CollectionResourceStatus, ImmutableResourceDiff, LocalCollectionOperation, OptimisticCollectionEntry, OptimisticCollectionOperation, OptimisticTerminalStatus, ResourceIncomingObject, ResourceIncomingValue, ResourceItem };
