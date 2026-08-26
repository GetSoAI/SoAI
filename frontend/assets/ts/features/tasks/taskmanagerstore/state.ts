/* SoAI - Tasks feature task manager store state [frontend/assets/ts/features/tasks/taskmanagerstore/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OperationEntry, PluginEntry, SubscriptionHandle } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';

type Listener = (store: TaskManagerStoreApi) => void;

interface TaskManagerStoreState {
    plugins: PluginEntry[];
    activePlugins: PluginEntry[];
    operations: Map<string, OperationEntry>;
    terminalTaskIds: Set<string>;
    listeners: Set<Listener>;
    pluginSubscription: SubscriptionHandle | null;
    operationUnsubscribe: (() => void) | null;
    operationSubscriptionTask: Promise<void> | null;
    operationReconciliationTask: Promise<void> | null;
    lifecycleGeneration: number;
    catalogNetworkFaultActive: boolean;
    pluginSnapshotSignature: string;
}

const createTaskManagerStoreState = (): TaskManagerStoreState => ({
    plugins: [],
    activePlugins: [],
    operations: new Map(),
    terminalTaskIds: new Set(),
    listeners: new Set(),
    pluginSubscription: null,
    operationUnsubscribe: null,
    operationSubscriptionTask: null,
    operationReconciliationTask: null,
    lifecycleGeneration: 0,
    catalogNetworkFaultActive: false,
    pluginSnapshotSignature: ''
});

export type { Listener, TaskManagerStoreState };
export { createTaskManagerStoreState };
