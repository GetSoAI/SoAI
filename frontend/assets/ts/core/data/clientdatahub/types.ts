/* SoAI - Normalized collection hub contracts [frontend/assets/ts/core/data/clientdatahub/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionResourceSnapshot, LocalCollectionOperation, OptimisticCollectionOperation, OptimisticTerminalStatus, ResourceIncomingObject, ResourceIncomingValue, ResourceItem } from '@core/data/clientdatahub/collectionResourceContracts.ts';
import type { ResourceStateListener } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ResourceDiff {
    added: string[];
    updated: string[];
    removed: string[];
}

interface ResourceMeta {
    source?: string | undefined;
    reason?: string | undefined;
    [key: string]: ResourceIncomingValue;
}

interface CollectionChannelDefinition {
    resource: string;
    trackBy: (item: ResourceItem) => string | null;
}

interface ClientDataHubDependencies {
    definitions: readonly CollectionChannelDefinition[];
    subscribeResourceState: (resource: string, listener: ResourceStateListener) => () => void;
    ensureResourceReady: (resource: string) => Promise<JsonValue | null>;
    refreshResource: (resource: string) => Promise<JsonValue | null>;
}

interface ClientDataHubSubscribeOptions {
    emitInitial?: boolean;
}

type ResourceListener = (snapshot: CollectionResourceSnapshot) => void;
type ResourceSnapshot = CollectionResourceSnapshot;
type ResourceChannelOptions = never;
type ResourceFieldValue = ResourceIncomingValue;
type OptimisticOperation = OptimisticCollectionOperation;
type OptimisticStatus = OptimisticTerminalStatus;
type ResourceOperation = LocalCollectionOperation;

export type { ClientDataHubDependencies, ClientDataHubSubscribeOptions, CollectionChannelDefinition, OptimisticOperation, OptimisticStatus, ResourceChannelOptions, ResourceDiff, ResourceFieldValue, ResourceIncomingObject, ResourceIncomingValue, ResourceItem, ResourceListener, ResourceMeta, ResourceOperation, ResourceSnapshot };
