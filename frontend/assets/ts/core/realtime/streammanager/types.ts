/* SoAI - Shared realtime stream manager contracts [frontend/assets/ts/core/realtime/streammanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiRequestBody, RequestOptions } from '@core/api/types/request.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { SystemLogSnapshot, TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import type { ErrorWithName, GpuSlotsBuilderResult, StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceReconciler } from '@core/realtime/streammanager/resources/resourceReconciler.ts';
import type { ResourceStateListener } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';

export type ResourceStatus = 'initializing' | 'unavailable' | 'ready' | 'recovering' | 'disconnected' | 'error';
export type ResourceUpdateOutcome = 'applied' | 'ignored' | 'rejected';

export type LoginCallback = (user: JsonValue | null) => void | Promise<void>;

export interface AuthManagerContract {
    isAuthenticated: boolean;
    onLogin: (callback: LoginCallback) => (() => void) | void;
    getWizardStatusSnapshot?: () => JsonValue | null;
}

export interface ConnectionStateContract {
    onChange: (listener: (baseUrl: string | null) => void, options?: { immediate?: boolean }) => () => void;
    whenReady?: (options?: { signal?: AbortSignal }) => Promise<string>;
}

export interface StreamManagerDependencies {
    apiClient: ApiServiceInterface;
    state: StateServiceInterface;
    connectionState: ConnectionStateContract;
    auth: AuthManagerContract | null;
}

export interface ResourceContext<ResourceValue extends JsonValue = JsonValue> {
    type: string;
    raw: JsonValue | null;
    resource: ResourceEntry<ResourceValue>;
    previousValue: ResourceValue | null;
}

export interface ResourceConfig<ResourceValue extends JsonValue = JsonValue> {
    autoStart: boolean;
    fetch: ((options?: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null>) | null;
    normalize: (data: JsonValue | null, context?: ResourceContext) => JsonValue | null;
    transform: (data: JsonValue | null, context?: ResourceContext) => ResourceValue | null;
    skipUnchangedTransform?: boolean;
    websocketOnly?: boolean;
}

export interface ResourceRegistrationConfig<ResourceValue extends JsonValue = JsonValue> extends Partial<ResourceConfig<ResourceValue>> {
    initialValue?: ResourceValue | null;
}

export interface StreamWebSocketClient {
    subscribeAll: (handler: (eventType: string, payload: JsonValue, context: WebSocketDispatchContext) => void | Promise<void>) => () => void;
    subscribe: (eventType: string, handler: (payload: JsonValue, context: WebSocketDispatchContext) => void | Promise<void>) => () => void;
    connect: () => void;
    isDestroyed?: () => boolean;
    sendMessage: (payload: JsonObject) => Promise<void>;
    waitForConnection: (timeoutMs?: number, options?: { signal?: AbortSignal | undefined }) => Promise<void>;
    requestSnapshot: (resource: string, parameters?: JsonObject | null, options?: { signal?: AbortSignal | undefined }) => Promise<{ data: JsonValue; resource: string; timestampMs: number | null } | null>;
}

export interface ResourceSnapshot<ResourceValue extends JsonValue = JsonValue> {
    name: string;
    value: ResourceValue | null;
    status: ResourceStatus;
    updatedAt?: number | null;
    error: Error | ErrorWithName | null;
}

export interface BundleSnapshotDetail {
    bundle: string;
    alias: string;
    resource: string;
    snapshot: ResourceSnapshot;
}

export interface ResourceListenerContext {
    type: string;
    raw?: JsonValue | null;
}

export type StreamSafeCallbackArgument = JsonValue | ResourceSnapshot | ResourceListenerContext | BundleSnapshotDetail | Error | ErrorWithName | null | undefined;
export type StreamSafeCallback = { callback(...inputArguments: StreamSafeCallbackArgument[]): void | Promise<void> }['callback'];

export type ResourceListener<ResourceValue extends JsonValue = JsonValue> = (snapshot: ResourceSnapshot<ResourceValue>, context: ResourceListenerContext) => void;
export interface ResourceSubscriptionOptions {
    immediate?: boolean;
    ensureStart?: boolean;
}

export interface ResourceSubscriptionRuntime {
    ready: boolean;
    acquireInterest(name: string): string | null;
    releaseInterest(token: string | null): void;
    startOwned(name: string): void;
}

export interface ResourceEntry<ResourceValue extends JsonValue = JsonValue> {
    name: string;
    value: ResourceValue | null;
    status: ResourceStatus;
    error: Error | null;
    warning: boolean;
    maintenance: boolean;
    updatedAt: number | null;
    configurationRevision: number;
    lastSnapshot: ResourceSnapshot<ResourceValue> | null;
    listeners: Set<ResourceListener<ResourceValue>>;
    typedSubscribers: Set<ResourceTypedSubscriber>;
    config: ResourceConfig<ResourceValue>;
    reconciler: ResourceReconciler;
    readonly pendingStart: true | null;
    reconciliationUnsubscribe: (() => void) | null;
}

export interface ResourceTypedSubscriber {
    listener: ResourceStateListener;
    initial: boolean;
    active: boolean;
    bindingRevision: number;
    unsubscribeReconciler: (() => void) | null;
}

export interface BundleDefinition {
    name: string;
    stateKey: string;
    resources: Record<string, string>;
    streams: string[];
}

export interface BundleHandlers {
    onReady?: (detail: { bundle: string; resources: string[] }) => void;
    onError?: (error: Error | string | null) => void;
    onAbort?: (detail: { bundle: string }) => void;
    onSnapshot?: (detail: BundleSnapshotDetail) => void;
    aliases?: Record<string, (payload: JsonValue | null) => void> | undefined;
}

export type OperationMetadata = JsonObject & {
    type: string;
    id: string;
    taskId?: string;
    endpoint?: string;
    startedAt?: number;
    message?: string;
    traceId?: string;
    convId?: string;
    conversationTitle?: string;
    model?: string;
    taskType?: string;
    taskStatus?: string;
    pluginName?: string;
};

export interface OperationEvent {
    id: string;
    type: string;
    status: string;
    meta: OperationMetadata;
    data: JsonObject;
    timestamp: number;
}

export type OperationListener = (event: OperationEvent) => void;

export type TaskTerminalEvent = JsonObject & {
    type: string;
    taskId: string;
    status: string;
    success: boolean;
    message: string;
    errorCode?: number | null;
    errorMessage?: string | null;
    meta?: OperationMetadata;
};

export type TaskTerminalListener = (event: TaskTerminalEvent) => void;

export interface StreamActionResult {
    accepted: Promise<string>;
    finished: Promise<JsonValue | null>;
    abort: () => void;
    close?: () => void;
    requestCancellation?: (reason: string | null) => Promise<TaskCancellationResponse>;
}

export interface TaskWatcher {
    handlers: StreamActionHandlers;
    resolve: (value: JsonValue | null) => void;
    reject: (reason: Error) => void;
    timeoutId: ReturnType<typeof setTimeout> | null;
    settled: boolean;
}

export interface AutoResourceState {
    status: string;
    error: { resource?: string; message?: string } | null;
    updatedAt: number;
}

export interface DiagnosticsSnapshot {
    queueDepth: number;
    resources: {
        name: string;
        status: ResourceStatus;
        pending: boolean;
        updatedAt: number | null;
        autoStart: boolean;
    }[];
    bundles: {
        name: string;
        ready: boolean;
        resources: { alias: string; name: string; status: string; pending: boolean }[];
    }[];
    ready: boolean;
}

export interface LogSnapshotResult {
    entries: JsonObject[];
    source: string;
    limit: number;
    receivedAt?: number;
}

export interface DeferredReadyOptions {
    deferTimeoutMs?: number;
}

export interface EnsureApiReadyOptions {
    timeoutMs?: number;
    allowDiscovery?: boolean;
    signal?: AbortSignal | null;
}

export interface StreamManagerMaintenanceState {
    active: boolean;
    reason?: string | null;
    resources: string[];
}

export interface _SubscribeHandlers {
    onOpen?: () => void;
    onConnect?: () => void;
    onMessage?: (payload: JsonValue | null, event: MessageEvent) => void;
    onInitial?: (payload: JsonValue | null, raw: JsonValue | null) => void;
    onUpdate?: (payload: JsonValue | null, type: string | null, raw: JsonValue | null) => void;
    onError?: (error: Error | string | null) => void;
    onClose?: () => void;
    onDisconnect?: () => void;
}

export interface ResourceFactoryManager {
    registerResource: (name: string, config: Partial<ResourceConfig> & { initialValue?: JsonValue | null }) => void;
    createApiFetcher: (endpoint: string) => (options?: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null>;
    createGpuSlotsResource: () => Partial<ResourceConfig<GpuSlotsBuilderResult>>;
}

export type ResourceFactory<ResourceValue extends JsonValue = JsonValue> = (manager: ResourceFactoryManager) => ResourceRegistrationConfig<ResourceValue>;

export interface StateServiceInterface {
    getTabState: (key: string) => JsonValue | null;
    setTabState: (key: string, value: JsonValue | null) => void;
}

export interface ApiServiceInterface {
    system: {
        logs: (source: string, options?: RequestOptions) => Promise<SystemLogSnapshot>;
        cancelTask?: (taskId: string, reason: string | null) => Promise<TaskCancellationResponse>;
    };
    request(method: string, endpoint: string, body?: ApiRequestBody, options?: RequestOptions): Promise<StreamTransportResponse>;
}

type StreamTransportResponse = ApiResponsePayload;
