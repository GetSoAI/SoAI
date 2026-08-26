/* SoAI - Tasks feature task manager types [frontend/assets/ts/features/tasks/taskmanager/taskManagerTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceListenerContext, ResourceSnapshot, TaskTerminalEvent } from '@core/realtime/streammanager/types.ts';
import type { TaskOperationEntry } from '@core/tasks/protocols.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody, RequestOptions } from '@core/api/types/request.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import type { OperationDefinition, OperationEntry, OperationEvent, OperationMeta, PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';

interface TaskManagerElements {
    manager: HTMLElement;
    toggle: HTMLElement;
    panel: HTMLElement;
    list: HTMLElement;
    stopAllButton: HTMLButtonElement;
    title: HTMLElement;
}

interface TaskManagerApi {
    post: (path: string, data?: ApiRequestBody, options?: RequestOptions) => Promise<ApiResponsePayload>;
}

interface TaskManagerStreamManager {
    resources: {
        ensureReady(options: { allowDiscovery: boolean }): Promise<void>;
        ensureResourceStarted(resource: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean }): Promise<JsonValue | null | undefined>;
    };
    subscriptions: {
        subscribeResourceState(resource: string, handler: (snapshot: ResourceSnapshot, context: ResourceListenerContext) => void, options: { immediate?: boolean; ensureStart?: boolean }): (() => void) | null;
    };
    tasks: {
        requestTaskCancellation(taskId: string, reason: string | null): Promise<TaskCancellationResponse>;
        taskAction(endpoint: string, options?: { method?: string; body?: ApiRequestBody; headers?: Record<string, string>; operation?: OperationMeta | null; allowDiscovery?: boolean; timeoutMs?: number }): { finished: Promise<JsonValue | null | undefined> };
        reconnectOperations(): Promise<void>;
        subscribeOperations(handler: (error: OperationEvent) => void): () => void;
        subscribeTerminalTasks(handler: (error: TaskTerminalEvent) => void): () => void;
    };
}

interface TaskManagerStoreApi {
    subscribe: (listener: (store: TaskManagerStoreApi) => void) => () => void;
    initialize: () => Promise<void>;
    reconcileOperations: () => Promise<void>;
    destroy: (...inputArguments: JsonValue[]) => Promise<boolean>;

    getActivePlugins: () => PluginEntry[];
    getStoppablePlugins: () => PluginEntry[];
    getStoppableCount: () => number;
    getActivePluginCount: () => number;
    getBlockingPluginCount: () => number;
    hasBlockingActivity: () => boolean;
    isPersistentStatus: (status: string) => boolean;

    getActiveOperations: () => OperationEntry[];
    getActiveOperationCount: () => number;
    getCancelableOperations: () => OperationEntry[];
    getCancelableOperationsForPluginKey: (pluginKey: string | null | undefined) => OperationEntry[];

    getPluginKey: (source: PluginEntry | string | null | undefined) => string | null;
    resolvePluginDisplayName: (plugin: PluginEntry) => string;
    getOperationsForPlugin: (plugin: PluginEntry | string) => OperationEntry[];
    getOperationDefinition: (type: string) => OperationDefinition | null;
    normalizeProgress: (value: JsonValue | null | undefined) => number;
    getOperationById: (id: string | null | undefined) => OperationEntry | null;
    removeOperationById: (id: string | null | undefined) => OperationEntry | null;
    upsertOperation: (operation: TaskOperationEntry | null | undefined) => void;
}

interface TaskManagerDependencies {
    dom: { getDocument: () => Document };
    statusManager: { createIndicator: (status: string) => HTMLElement };
    apiClient: TaskManagerApi;
    stream: TaskManagerStreamManager;
    createStore: () => TaskManagerStoreApi;
    storage: { get: (key: string, defaultValue?: JsonValue | null) => JsonValue | null; set: (key: string, value: JsonValue | null) => void };
}

export type { TaskManagerStoreApi, OperationEntry, OperationMeta, PluginEntry, TaskManagerApi, TaskManagerDependencies, TaskManagerElements, TaskManagerStreamManager };
