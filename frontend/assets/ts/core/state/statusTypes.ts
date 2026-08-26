/* SoAI - Shared state status types [frontend/assets/ts/core/state/statusTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceListener, ResourceSnapshot, ResourceSubscriptionOptions } from '@core/realtime/streammanager/types.ts';

export type StatusKey = string;

export type StatusInput = JsonValue | undefined;

export interface StatusStreamSnapshot {
    value?: StatusInput;
    status?: string | number;
}

export interface StreamManagerForStatus {
    resources: {
        getResource(streamId: string, options?: { state?: boolean }): ResourceSnapshot | JsonValue | null;
    };
    subscriptions: {
        subscribeResourceState(streamId: string, callback: ResourceListener, options?: ResourceSubscriptionOptions): () => void;
    };
}
