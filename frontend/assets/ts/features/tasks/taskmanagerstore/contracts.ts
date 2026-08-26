/* SoAI - Tasks feature task manager store contracts [frontend/assets/ts/features/tasks/taskmanagerstore/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceListenerContext, ResourceSnapshot, TaskTerminalEvent } from '@core/realtime/streammanager/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { OperationDefinition, OperationEntry, OperationEvent, PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { TaskManagerStreamManager } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface TaskManagerStoreDependencies {
    stream: TaskManagerStreamManager;
}

interface OperationSubscriptionHost {
    subscribeOperations: (handler: (error: OperationEvent) => void) => () => void;
    subscribeTerminalTasks: (handler: (error: TaskTerminalEvent) => void) => () => void;
}

interface OperationReconciliationHost {
    reconnectOperations: () => Promise<void>;
}

interface PluginResourceSubscriptionHost {
    subscribeResourceState(resource: string, handler: (snapshot: ResourceSnapshot, context: ResourceListenerContext) => void, options: { immediate?: boolean; ensureStart?: boolean }): (() => void) | null;
    ensureResourceStarted(resource: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean }): Promise<JsonValue | null | undefined>;
}

interface PluginUpdateContext {
    pluginKey: (source: PluginEntry | string | null | undefined) => string | null;
}

interface OperationEventContext {
    getDefinition: (type: string | null | undefined) => OperationDefinition | null;
    getPluginKey: (name: string | null | undefined) => string | null;
    getExistingOperation: (id: string) => OperationEntry | null;
    normalizeProgress: (value: JsonValue | null | undefined) => number | null;
}

export type { OperationEventContext, OperationReconciliationHost, OperationSubscriptionHost, PluginResourceSubscriptionHost, PluginUpdateContext, TaskManagerStoreDependencies };
