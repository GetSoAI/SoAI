/* SoAI - Tasks feature task manager models [frontend/assets/ts/features/tasks/taskmanager/taskManagerModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface PluginEntry {
    name?: string | undefined;
    displayName?: string | undefined;
    identifier?: string | undefined;
    plugin?: string | undefined;
    state?: string | undefined;
    isPersistent?: boolean | undefined;
    __pluginKey?: string | undefined;
    __synthetic?: boolean | undefined;
}

interface OperationDefinition {
    cancelable: boolean;
}

type OperationMeta = JsonObject & {
    plugin?: string;
    pluginName?: string;
    provider?: string;
    sourcePlugin?: string;
    universalId?: string;
    url?: string;
    cancelable?: boolean;
    convId?: string;
    conversationTitle?: string;
    model?: string;
    tokenCount?: number;
    operationId?: string;
    taskId?: string;
    taskStatus?: string;
    displayName?: string;
};

interface OperationEntry {
    id: string;
    type: string;
    pluginKey?: string | undefined;
    pluginName?: string | undefined;
    meta?: OperationMeta | undefined;
    cancelable?: boolean | undefined;
    progress?: number | undefined;
    isLocal?: boolean | undefined;
}

interface OperationEvent {
    id?: string | undefined;
    status?: string | undefined;
    type?: string | undefined;
    meta?: OperationMeta | undefined;
    data?: (JsonObject & { progress?: JsonValue | undefined; message?: string | undefined; details?: string | undefined }) | undefined;
}

interface SubscriptionHandle {
    abort?: () => void;
    unsubscribe?: () => void;
    ready?: Promise<void> | undefined;
}

interface CatalogSubscription {
    plugins: (value: PluginEntry[] | { value: PluginEntry[] }) => void;
    onError: (error: Error | JsonValue | null) => void;
}

export type { CatalogSubscription, OperationDefinition, OperationEntry, OperationEvent, OperationMeta, PluginEntry, SubscriptionHandle };
