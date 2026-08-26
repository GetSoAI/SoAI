/* SoAI - Shared realtime contracts [frontend/assets/ts/core/realtime/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ErrorWithName } from '@core/types/streamTypes.ts';

type RealtimePayload = Error | ErrorWithName | JsonValue | null | undefined;
type SubscriptionHandler = ((...inputArguments: RealtimePayload[]) => void) | null | undefined;
type SubscriptionHandlers = Record<string, SubscriptionHandler>;
type SubscriptionHandle =
    | (() => void)
    | {
          unsubscribe?: () => void;
          stop?: () => void;
          abort?: () => void;
          cancel?: () => void;
          close?: () => void;
      }
    | string
    | null
    | undefined;

interface SubscriptionOptions {
    key?: string;
    resource?: string;
    endpoint?: string;
    handlers?: SubscriptionHandlers;
    wrapHandlers?: (handlers: SubscriptionHandlers) => SubscriptionHandlers | undefined;
    decorate?: (handlers: SubscriptionHandlers) => SubscriptionHandlers | undefined;
    subscribe?: (handlers: SubscriptionHandlers, options?: SubscriptionOptions) => SubscriptionHandle;
    immediate?: boolean;
    streamManager?: StreamManagerInterface | null;
    onUnavailable?: () => void;
}

interface SubscriptionContext {
    type: string;
    raw?: RealtimePayload;
}

interface SubscriptionSnapshot {
    value?: JsonValue | null;
    error?: Error | ErrorWithName | JsonValue | null;
}

interface SubscriptionController {
    owner: WeakKey;
    key: string | undefined;
    stop(): void;
    restart(extraOptions?: Partial<SubscriptionOptions>): SubscriptionController;
    isActive(): boolean;
    getOptions(): SubscriptionOptions;
    getHandlers(): SubscriptionHandlers;
}

interface OwnerState {
    subscriptions: Map<string, SubscriptionController>;
}

interface StreamManagerInterface {
    subscribeResourceState?: (resource: string, listener: (snapshot: SubscriptionSnapshot, context: SubscriptionContext) => void, options?: { immediate?: boolean; ensureStart?: boolean }) => SubscriptionHandle;
    unsubscribe?: (target: string) => void;
}

export type { RealtimePayload, SubscriptionHandle, SubscriptionHandler, SubscriptionHandlers, SubscriptionOptions, SubscriptionContext, SubscriptionSnapshot, SubscriptionController, OwnerState, StreamManagerInterface };
