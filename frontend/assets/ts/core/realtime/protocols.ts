/* SoAI - Shared realtime protocols [frontend/assets/ts/core/realtime/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceListenerContext, ResourceSnapshot } from '@core/realtime/streammanager/types.ts';

interface StreamBundleSubscription {
    ready?: Promise<JsonValue | null | undefined> | undefined;
    abort?: (() => void) | undefined;
    unsubscribe?: (() => void) | undefined;
}

interface BundleSubscriptionStreamManager {
    subscribeToBundle: (bundle: string, handlers: Record<string, JsonValue | null | undefined>, options?: Record<string, JsonValue | null | undefined>) => StreamBundleSubscription | null;
}

interface ResourceReadStreamManager {
    getResource: (name: string, options?: { state?: boolean }) => JsonValue | null | undefined;
}

interface ResourceLifecycleStreamManager {
    ensureResourceStarted: (name: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean }) => Promise<JsonValue | null>;
    subscribe: (name: string, listener: (snapshot: ResourceSnapshot, context: ResourceListenerContext) => void, options?: { immediate?: boolean; ensureStart?: boolean }) => () => void;
    refresh: (name: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean }) => Promise<JsonValue | null>;
}

type BundleResourceStreamManager = BundleSubscriptionStreamManager & ResourceReadStreamManager;
export type { BundleResourceStreamManager, BundleSubscriptionStreamManager, ResourceLifecycleStreamManager, ResourceReadStreamManager, StreamBundleSubscription };
