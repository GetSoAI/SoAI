/* SoAI - Shared routing stream contracts [frontend/assets/ts/core/routing/pages/pagetypes/stream/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceSubscriptionHandler, SubscriptionHandler } from '@core/subscriptionmanager/contracts.ts';

export interface StreamActionHandle {
    abort: () => void;
    accepted?: Promise<string>;
    finished: Promise<StreamFinishedValue>;
    close?: () => void;
}

export interface StreamCompletionStatus {
    cancelled?: boolean;
    success?: boolean;
    message?: string;
}

export type StreamFinishedValue = JsonValue | StreamCompletionStatus | null;

export type StreamHandle =
    | (() => void)
    | {
          abort?: () => void;
          cancel?: () => void;
          stop?: () => void;
          unsubscribe?: () => void;
          close?: () => void;
          finished?: Promise<StreamFinishedValue>;
          handle?: StreamActionHandle;
          cleanup?: () => void;
      };

export interface StreamHandleTrackerContract {
    active: Map<string, StreamHandle>;
    size: number;
    has(key: string): boolean;
    track(key: string, stream: StreamHandle): StreamHandle;
    release(key: string, options?: { cancel?: boolean }): void;
    clear(options?: { abort?: boolean; cancel?: boolean }): void;
}

export interface StreamHandlerCallbacks {
    onProgress?: (data: JsonValue | null) => void;
    onComplete?: (data: JsonValue | null) => void;
    onError?: (error: Error | JsonValue | null) => void;
}

export interface StreamProgressData {
    progress?: number | null;
    message?: string | null;
    details?: JsonValue | null;
    state?: 'info' | 'success' | 'error';
    key?: string;
    type?: string;
}

export interface EnsureCollectionStreamOptions {
    collectionKey?: string;
    streamManager?: StreamResourceLoader;
    allowDiscovery?: boolean;
    signal?: AbortSignal | undefined;
}

export interface SubscriptionManager {
    subscribeResourceState(key: string, handler: ResourceSubscriptionHandler): () => void;
    subscribeResourceValue(key: string, handler: SubscriptionHandler): () => void;
    subscribeWebSocket(event: string, handler: (data: JsonValue | null) => void): () => void;
    unsubscribeResource(key: string): void;
    unsubscribeWebSocket(event: string): void;
    ensureReady(options?: { signal?: AbortSignal }): Promise<void>;
    verifyReady(): Promise<void>;
    getHealthStatus(): Array<{ key: string; active: boolean; errors: number }>;
    destroy(): void;
}

export interface SubscriptionEntry {
    key?: string;
    name?: string;
    stream?: string;
    handler?: (data: JsonValue | null) => void;
    callback?: (data: JsonValue | null) => void;
}
