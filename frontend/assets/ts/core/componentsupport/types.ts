/* SoAI - Shared component support contracts [frontend/assets/ts/core/componentsupport/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RealtimeConfig } from '@core/realtime/collectionContracts.ts';
import type { CollectionsStore, CollectionsStoreOptions, StoreItemRecord } from '@core/CollectionsStore.ts';
import type { CollectionRuntime } from '@core/data/collectionview/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ErrorWithName } from '@core/types/streamTypes.ts';

type LogLevel = 'warn' | 'error' | 'debug';

type Reporter = (context: string, message: string, error?: Error | ErrorWithName | JsonValue | null | undefined) => void;

interface ComponentInstance {
    initialize?: ((options?: { force?: boolean | undefined }) => Promise<void | boolean> | void | boolean) | undefined;
    destroy?: (() => Promise<void | boolean> | void | boolean) | undefined;
}

interface RegistryOptions {
    autoInitialize?: boolean;
    priority?: number;
}

interface ComponentMeta {
    component: ComponentInstance;
    options: Required<RegistryOptions>;
    initialized: boolean;
    initializing: boolean;
    initialization: Promise<void> | null;
}

interface CollectionConfigOptions {
    collectionOptions?: CollectionsStoreOptions<StoreItemRecord>;
    hiddenClass?: string;
    realtime?: RealtimeConfig;
}

interface PageInstance {
    collection?: CollectionRuntime | CollectionsStore<StoreItemRecord> | null;
    showLoading?: (message?: string) => string;
}

export type { CollectionConfigOptions, ComponentInstance, ComponentMeta, LogLevel, PageInstance, RealtimeConfig, RegistryOptions, Reporter };
