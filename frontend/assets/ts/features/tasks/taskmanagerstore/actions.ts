/* SoAI - Tasks feature task manager store actions [frontend/assets/ts/features/tasks/taskmanagerstore/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { OperationDefinition, OperationEntry, PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';
import { OPERATION_TYPE_CONFIG } from '@features/tasks/taskmanagerstore/constants.ts';
import { isActiveStatus, isBlockingPluginStatus, isPersistentStatus, shouldShowProgress } from '@features/tasks/taskmanagerstore/statusProgress.ts';
import type { TaskManagerStoreState } from '@features/tasks/taskmanagerstore/state.ts';

const getPlugins = (state: TaskManagerStoreState): PluginEntry[] => state.plugins;

const getActivePlugins = (state: TaskManagerStoreState): PluginEntry[] => state.activePlugins;

const getStoppablePlugins = (state: TaskManagerStoreState, isPersistentPlugin: (plugin: PluginEntry) => boolean): PluginEntry[] => {
    const stoppable: PluginEntry[] = [];
    for (const plugin of state.activePlugins) {
        if (!isPersistentPlugin(plugin)) {
            stoppable.push(plugin);
        }
    }
    return stoppable;
};

const getOperationCountForPlugin = (state: TaskManagerStoreState, plugin: PluginEntry | string, resolvePluginKey: (source: PluginEntry | string | null | undefined) => string | null): OperationEntry[] => {
    const pluginKey = resolvePluginKey(plugin);
    const operations: OperationEntry[] = [];
    if (!pluginKey) {
        return operations;
    }

    state.operations.forEach((operation) => {
        if (operation?.pluginKey === pluginKey) {
            operations.push(operation);
        }
    });

    return operations;
};

const getActiveOperations = (state: TaskManagerStoreState): OperationEntry[] => Array.from(state.operations.values());

const getActiveOperationCount = (state: TaskManagerStoreState): number => state.operations.size;

const getCancelableOperations = (state: TaskManagerStoreState): OperationEntry[] => getActiveOperations(state).filter((operation) => operation?.cancelable);

const getCancelableOperationsForPluginKey = (state: TaskManagerStoreState, pluginKey: string | null | undefined): OperationEntry[] => {
    if (!pluginKey) {
        return [];
    }

    return getActiveOperations(state).filter((operation) => operation?.pluginKey === pluginKey && operation.cancelable);
};

const getOperationById = (state: TaskManagerStoreState, operationId: string | null | undefined): OperationEntry | null => {
    if (!operationId) {
        return null;
    }
    return state.operations.get(operationId) || null;
};

const getActivePluginCount = (state: TaskManagerStoreState, resolvePluginKey: (source: PluginEntry | string | null | undefined) => string | null): number => {
    const pluginKeys = new Set<string>();
    for (const plugin of state.activePlugins) {
        const pluginKey = resolvePluginKey(plugin);
        if (pluginKey) {
            pluginKeys.add(pluginKey);
        }
    }
    state.operations.forEach((operation) => {
        if (operation?.pluginKey) {
            pluginKeys.add(operation.pluginKey);
        }
    });
    return pluginKeys.size;
};

const getBlockingPluginCount = (state: TaskManagerStoreState, normalizeStatus: (status: string | null | undefined) => string): number => {
    return state.activePlugins.reduce((count, plugin) => count + (isBlockingPluginStatus(plugin.state, normalizeStatus) ? 1 : 0), 0);
};

const hasBlockingActivity = (state: TaskManagerStoreState, normalizeStatus: (status: string | null | undefined) => string): boolean => {
    if (state.operations.size > 0) {
        return true;
    }

    for (const plugin of state.activePlugins) {
        if (isBlockingPluginStatus(plugin.state, normalizeStatus)) {
            return true;
        }
    }
    return false;
};

const getOperationDefinition = (type: string | null | undefined): OperationDefinition | null => {
    if (!isString(type)) return null;
    const normalized = type.trim();
    if (!normalized) return null;
    return OPERATION_TYPE_CONFIG[normalized] || { cancelable: true };
};

export { getActiveOperationCount, getActiveOperations, getActivePluginCount, getActivePlugins, getBlockingPluginCount, getCancelableOperations, getCancelableOperationsForPluginKey, getOperationById, getOperationCountForPlugin, getOperationDefinition, getPlugins, getStoppablePlugins, hasBlockingActivity, isActiveStatus, isPersistentStatus, shouldShowProgress };
