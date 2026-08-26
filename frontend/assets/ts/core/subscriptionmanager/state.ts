/* SoAI - Shared subscription manager state [frontend/assets/ts/core/subscriptionmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { type PendingSubscriptionStart, type SubscriptionHealth, type UnsubscribeEntry, type UnsubscribeFunction, type StreamManagerInterface } from '@core/subscriptionmanager/contracts.ts';

interface SubscriptionManagerState {
    subscriptions: Map<string, UnsubscribeEntry>;
    health: Map<string, SubscriptionHealth>;
    streamManager: StreamManagerInterface | null;
    timers: ResourceTracker | null;
    pendingStarts: Map<string, PendingSubscriptionStart>;
    wsSubscriptions: Map<string, UnsubscribeFunction>;
}

const createSubscriptionManagerState = (): SubscriptionManagerState => ({
    subscriptions: new Map(),
    health: new Map(),
    streamManager: null,
    timers: null,
    pendingStarts: new Map(),
    wsSubscriptions: new Map()
});

export { createSubscriptionManagerState };
export type { SubscriptionManagerState };
