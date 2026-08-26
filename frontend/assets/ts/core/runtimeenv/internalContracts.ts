/* SoAI - Shared runtime environment internal contracts [frontend/assets/ts/core/runtimeenv/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { Deferred } from '@core/runtime/deferred.ts';

type RuntimeMessagePayload = JsonObject;

export interface StreamManagerInterface {
    resources: {
        ensureReady(options?: { allowDiscovery?: boolean; signal?: AbortSignal | undefined }): Promise<void>;
        startAuto(options?: { signal?: AbortSignal | undefined }): Promise<Array<JsonValue | null>>;
        ensureResourceStarted(resource: string, options?: { signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
    };
    subscriptions: {
        subscribeBundle(bundleName: string, handlers: JsonObject, options?: { signal?: AbortSignal | null }): DetachedSubscription;
    };
}

export interface DetachedSubscription {
    ready: Promise<void>;
}

export interface StateManagerInterface {
    snapshotTabState(): JsonObject;
    setTabState(key: string, value: JsonValue): void;
}

export interface EventHubInterface {
    addEventListener(event: string, handler: (event: Event) => void, options?: AddEventListenerOptions): void;
    removeEventListener(event: string, handler: (event: Event) => void): void;
}

export interface BroadcastChannelInterface {
    addEventListener?: ((event: string, handler: (event: MessageEvent) => void) => void) | undefined;
    onmessage?: ((event: MessageEvent) => void) | null | undefined;
    postMessage(message: JsonValue): void;
    close(): void;
}

export interface CoordinatorMessage {
    type: string;
    payload?: RuntimeMessagePayload;
    source: string;
    target: string;
}

export type WindowMetadata = JsonObject & {
    pageId: string | null;
    parameters: JsonObject;
};

export interface WindowRecord {
    window: Window | null;
    pageId: string | null;
    openedAt: number;
    monitorId: number | null;
    metadata: WindowMetadata;
}

export interface DetachedContext {
    windowId: string;
    metadata: WindowMetadata;
    timestamp: number;
    state: JsonObject;
}

export interface OpenWindowInfo {
    windowId: string;
    pageId: string;
    openedAt: number;
}

export interface OpenDetachedOptions {
    title?: string;
    parameters?: JsonObject;
}

export interface OpenDetachedResult {
    windowId: string;
    window: Window | null;
    close: () => boolean;
}

export interface RuntimeEnvInterface {
    readonly kernel: {
        initialized: boolean;
        bootPromise: Promise<boolean> | null;
        start: () => Promise<boolean>;
        initialize: () => Promise<boolean>;
        refresh: () => Promise<boolean>;
    };
    readonly windowService: {
        awaitDetachedContext: (options?: { timeout?: number }) => Promise<boolean>;
        getDetachedContext: () => DetachedContext | null;
        getDetachedMetadata: () => WindowMetadata | null;
        notifyDetachedClosed: (windowId?: string) => void;
        openDetached: (pageId: string, options?: OpenDetachedOptions) => OpenDetachedResult | null;
        focusByPage: (pageId: string) => boolean;
        closeWindow: (windowId: string) => boolean;
        closeAllWindows: () => void;
        getOpenWindows: () => OpenWindowInfo[];
        isWindowOpen: (windowId: string) => boolean;
    };
    readonly runtimeState?: JsonObject | null;
}

export interface RuntimeWindowServiceState {
    openWindows: Map<string, WindowRecord>;
    pendingMetadata: Map<string, WindowMetadata>;
    windowId: string;
    hostWindowId: string;
    isPrimaryWindow: boolean;
    contextDeferred: Deferred<boolean> | null;
    contextPromise: Promise<boolean> | null;
    pendingContext: DetachedContext | null;
    detachedContext: DetachedContext | null;
    detachedWarmupTask: Promise<void> | null;
    detachedSubscription: DetachedSubscription | null;
    logSnapshotTask: Promise<void> | null;
}
