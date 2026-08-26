/* SoAI - Shared realtime collection contracts [frontend/assets/ts/core/realtime/collectionContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionsStore, StoreItemRecord } from '@core/CollectionsStore.ts';
import type { RealtimeLifecycleArgument, RealtimeLifecycleHandlers } from '@core/componentsupport/realtimeLifecycle.ts';
import type { CollectionRuntime } from '@core/data/collectionview/types.ts';
import type { SubscriptionHandle, SubscriptionHandlers, SubscriptionOptions } from '@core/realtime/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ManagedSubscription {
    stop: () => void;
    isActive?: () => boolean;
}

interface RealtimeCollectionConfig extends RealtimeLifecycleHandlers {
    key?: string;
    endpoint?: string;
    resource?: string;
    subscribe: (handlers: SubscriptionHandlers, options?: SubscriptionOptions) => SubscriptionHandle;
    decorate?: (handlers: SubscriptionHandlers) => SubscriptionHandlers | undefined;
    immediate?: boolean;
    autoStart?: boolean;
}

interface RealtimeCollectionRuntimeConfig extends RealtimeCollectionConfig {
    fetch?: () => Promise<JsonValue | null>;
}

interface RealtimePageInstance {
    collection?: CollectionRuntime | CollectionsStore<StoreItemRecord> | null;
    showLoading?: (message?: string) => string;
}

interface RealtimeConfig extends RealtimeCollectionConfig {
    onData?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    handlers?: SubscriptionHandlers;
    fetch?: (page: RealtimePageInstance) => Promise<JsonValue | null>;
}

export type { ManagedSubscription, RealtimeCollectionConfig, RealtimeCollectionRuntimeConfig, RealtimeConfig };
