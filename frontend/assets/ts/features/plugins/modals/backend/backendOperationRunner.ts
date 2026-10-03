/* SoAI - Plugins feature backend operation runner [frontend/assets/ts/features/plugins/modals/backend/backendOperationRunner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { executeMutationWithClockRecovery } from '@core/mutations/mutationExecution.ts';
import { serializeBackendWebSocketCommand, type BackendWebSocketCommandType } from '@core/plugins/pluginMutationContracts.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { BackendOperationHost } from '@features/plugins/modals/backend/backendTypes.ts';
import { PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_STOPPED } from '@core/state/pluginStatus.ts';

interface ExecuteBackendOperationConfig {
    commandType: BackendWebSocketCommandType;
    deleteModels?: boolean;
    backendVariantId?: string;
    operationMeta: { type: string };
    loadingMessage: string;
    failMessage: string;
    onAccepted?: (taskId: string) => void;
}

interface RunBackendOperationConfig extends ExecuteBackendOperationConfig {
    okMessage: string;
    onBefore?: () => void;
    onAfter?: () => void;
    onSuccess?: () => void;
    onFailure?: () => void;
}

type BackendOperationOutcome = { status: 'succeeded'; isCompleteEvent: boolean; message: string; taskId: string } | { status: 'cancelled' | 'detached'; taskId: string } | { status: 'failed'; error: Error | null; taskId: string | null };

const requirePluginName = (plugin: PluginRecord): string => {
    const name = toTrimmedString(plugin.name);
    if (!name) {
        throw new Error('Backend operation requires a plugin name');
    }
    return name;
};

const resolvePluginDisplayName = (host: BackendOperationHost, plugin: PluginRecord): string => {
    const displayName = String(plugin.displayName ?? '').trim();
    if (displayName) return displayName;
    const name = requirePluginName(plugin);
    return host.formatPluginName(name) || name;
};

const executeBackendOperation = async (host: BackendOperationHost, plugin: PluginRecord, config: ExecuteBackendOperationConfig): Promise<BackendOperationOutcome> => {
    const pluginName = requirePluginName(plugin);
    const displayName = resolvePluginDisplayName(host, plugin);
    const message = toTrimmedString(config.loadingMessage);
    const operationKeyPrefix = `${config.operationMeta.type}-${pluginName}`;
    const handlers = host.createStreamHandlers(operationKeyPrefix, config.operationMeta.type);
    let acceptedTaskId: string | null = null;
    try {
        const backendVariantId = toTrimmedString(config.backendVariantId);
        const mutationOperationKey = `plugin:${pluginName}:backend-lifecycle`;
        const accepted = await executeMutationWithClockRecovery(async (taskId) => {
            const command = serializeBackendWebSocketCommand({
                commandType: config.commandType,
                pluginName,
                ...(config.commandType === 'plugin_backend_remove' ? { deleteModels: config.deleteModels } : {}),
                ...(backendVariantId ? { backendVariantId } : {})
            });
            const stream = await host.startTaskCommand(
                {
                    ...command,
                    'task_id': taskId
                },
                {
                    handlers,
                    operation: {
                        type: config.operationMeta.type,
                        pluginName,
                        plugin: pluginName,
                        displayName,
                        message,
                        cancelable: true,
                        operationKey: mutationOperationKey,
                        requestId: taskId
                    }
                }
            );
            if (!stream.accepted) throw new Error('Backend task did not expose accepted task ownership');
            return { stream, taskId: await stream.accepted };
        });
        const taskId = accepted.taskId;
        acceptedTaskId = taskId;
        host.beginOptimisticOperation({
            operationId: taskId,
            itemId: pluginName,
            desiredItem: {
                state: config.commandType === 'plugin_backend_remove' ? PLUGIN_STATUS_BACKEND_NOT_INSTALLED : PLUGIN_STATUS_STOPPED
            },
            acceptedTaskId: taskId
        });
        config.onAccepted?.(taskId);
        const settled = await settleTrackedTaskStream({
            tracker: host.streams,
            stream: accepted.stream,
            keyPrefix: operationKeyPrefix,
            failMessage: config.failMessage
        });
        if (settled.cancelled) return { status: 'cancelled', taskId };
        if (settled.detached) return { status: 'detached', taskId };
        if (!settled.record) return { status: 'failed', error: null, taskId };
        return { status: 'succeeded', isCompleteEvent: settled.isCompleteEvent, message: settled.message, taskId };
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('BackendManager', 'Backend operation failed', runtimeError);
        return { status: 'failed', error: runtimeError, taskId: acceptedTaskId };
    }
};

const runBackendOperation = async (host: BackendOperationHost, plugin: PluginRecord, config: RunBackendOperationConfig): Promise<void> => {
    requirePluginName(plugin);
    if (config.onBefore) config.onBefore();
    let outcome: BackendOperationOutcome;
    try {
        outcome = await executeBackendOperation(host, plugin, config);
        if (outcome.status === 'failed' && outcome.error !== null) {
            showOperationFailureNotification({
                error: outcome.error,
                fallbackMessage: toTrimmedString(config.failMessage) || i18n.t('common.errors.unknownError'),
                rawMessage: true,
                showNotification: (message, level): void => host.showNotification(message, level)
            });
        }
    } finally {
        if (config.onAfter) config.onAfter();
    }

    if (outcome.status !== 'succeeded') {
        if (outcome.status === 'failed' && config.onFailure) config.onFailure();
        return;
    }

    const defaultOk = toTrimmedString(config.okMessage);
    const okMessage = outcome.message || defaultOk;
    host.showNotification(okMessage, outcome.isCompleteEvent ? 'success' : 'info');
    if (outcome.isCompleteEvent && config.onSuccess) config.onSuccess();
};

export { executeBackendOperation, runBackendOperation };
export type { BackendOperationOutcome, ExecuteBackendOperationConfig };
