/* SoAI - Typed page subscription ownership contracts [frontend/assets/ts/core/subscriptionmanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceReconciliationSnapshot, ResourceStateDeliveryContext } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ResourceSubscriptionSnapshot {
    name?: string;
    value?: JsonValue | null;
    status?: string;
    updatedAt?: number | null;
    error?: Error | null;
}

interface StreamManagerInterface {
    resources: {
        ensureReady(options?: { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined }): Promise<void>;
        ensureResourceStarted(key: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
        getResource(key: string, options?: { state?: boolean }): ResourceSubscriptionSnapshot | JsonValue | undefined | null;
    };
    subscriptions: {
        subscribeResourceState(key: string, handler: ResourceSubscriptionHandler, options?: { immediate?: boolean; ensureStart?: boolean }): UnsubscribeFunction | void;
        subscribeResourceValue(key: string, handler: SubscriptionHandler, options?: { immediate?: boolean; ensureStart?: boolean }): UnsubscribeFunction | void;
        unsubscribe(entry: UnsubscribeEntry): void;
    };
}

type SubscriptionContext = ResourceStateDeliveryContext;
type SubscriptionHandler = (value: JsonValue | null, context: SubscriptionContext) => void;
type ResourceSubscriptionHandler = (snapshot: ResourceReconciliationSnapshot, context: SubscriptionContext) => void;
type SubscriptionSnapshot = ResourceReconciliationSnapshot;
type UnsubscribeFunction = () => void;
type UnsubscribeEntry = UnsubscribeFunction | { unsubscribe(): void } | { stop(): void } | { abort(): void } | { cancel(): void } | { close(): void } | string | null | undefined | void;

interface SubscriptionHealth {
    active: boolean;
    errors: number;
    readyChecked: boolean;
    resourceStarted: boolean;
    version: number;
}

interface PendingSubscriptionStart {
    controller: AbortController;
    promise: Promise<void>;
}

interface HealthStatus {
    key: string;
    active: boolean;
    errors: number;
}

interface SubscriptionManagerDependencies {
    streamManager?: StreamManagerInterface;
}

export type { HealthStatus, PendingSubscriptionStart, ResourceSubscriptionHandler, ResourceSubscriptionSnapshot, StreamManagerInterface, SubscriptionContext, SubscriptionHandler, SubscriptionManagerDependencies, SubscriptionSnapshot, SubscriptionHealth, UnsubscribeEntry, UnsubscribeFunction };
