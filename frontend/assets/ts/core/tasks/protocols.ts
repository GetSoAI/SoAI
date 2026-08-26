/* SoAI - Shared tasks protocols [frontend/assets/ts/core/tasks/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

type TaskOperationMeta = JsonObject;

interface TaskOperationEntry {
    id: string;
    type: string;
    pluginKey?: string | undefined;
    pluginName?: string | undefined;
    meta?: TaskOperationMeta | undefined;
    cancelable?: boolean | undefined;
    progress?: number | undefined;
    isLocal?: boolean | undefined;
}

interface TaskOperationFilter {
    types?: readonly string[] | undefined;
    pluginKey?: string | null | undefined;
    pluginName?: string | null | undefined;
    conversationId?: string | null | undefined;
}

interface TaskLocalOperationUpdate {
    id: string;
    type: string;
    pluginName?: string | null | undefined;
    pluginKey?: string | null | undefined;
    meta?: TaskOperationMeta | undefined;
    cancelable?: boolean | undefined;
    progress?: number | undefined;
    cancel?: (() => void | Promise<void>) | undefined;
}

type TaskOperationListener = (operations: TaskOperationEntry[]) => void;

interface TaskOperationsApi {
    getOperations(filter?: TaskOperationFilter): TaskOperationEntry[];
    subscribeOperations(filter: TaskOperationFilter, listener: TaskOperationListener): () => void;
    reconcileOperations(): Promise<void>;
    cancelOperationById(operationId: string): Promise<void>;
    getPluginKey(source: string | null | undefined): string | null;
    upsertLocalOperation(update: TaskLocalOperationUpdate): void;
    removeLocalOperation(operationId: string): void;
}

const TASK_MANAGER_SERVICE_ID = 'features.tasks.manager';

export { TASK_MANAGER_SERVICE_ID };
export type { TaskLocalOperationUpdate, TaskOperationEntry, TaskOperationFilter, TaskOperationListener, TaskOperationMeta, TaskOperationsApi };
