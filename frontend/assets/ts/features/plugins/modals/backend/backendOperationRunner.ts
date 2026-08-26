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

interface RunBackendOperationConfig {
    commandType: BackendWebSocketCommandType;
    deleteModels?: boolean;
    backendVariantId?: string;
    operationMeta: { type: string };
    loadingMessage: string;
    okMessage: string;
    failMessage: string;
    onBefore?: () => void;
    onAfter?: () => void;
    onSuccess?: () => void;
    onFailure?: () => void;
}

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

const runBackendOperation = async (host: BackendOperationHost, plugin: PluginRecord, config: RunBackendOperationConfig): Promise<void> => {
    const pluginName = requirePluginName(plugin);
    const displayName = resolvePluginDisplayName(host, plugin);
    const message = toTrimmedString(config.loadingMessage);
    const operationKeyPrefix = `${config.operationMeta.type}-${pluginName}`;
    const handlers = host.createStreamHandlers(operationKeyPrefix, config.operationMeta.type);

    if (config.onBefore) config.onBefore();

    let cancelled = false;
    let detached = false;
    let success = false;
    let completionMessage = '';
    let isCompleteEvent = false;
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
        const stream = accepted.stream;
        const acceptedTaskId = accepted.taskId;
        host.beginOptimisticOperation({
            operationId: acceptedTaskId,
            itemId: pluginName,
            desiredItem: {
                state: config.commandType === 'plugin_backend_remove' ? PLUGIN_STATUS_BACKEND_NOT_INSTALLED : PLUGIN_STATUS_STOPPED
            },
            acceptedTaskId
        });
        const settled = await settleTrackedTaskStream({
            tracker: host.streams,
            stream,
            keyPrefix: operationKeyPrefix,
            failMessage: config.failMessage
        });
        cancelled = settled.cancelled;
        detached = settled.detached;
        completionMessage = settled.message;
        isCompleteEvent = settled.isCompleteEvent;
        success = !cancelled && Boolean(settled.record);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('BackendManager', 'Backend operation failed', runtimeError);
        showOperationFailureNotification({
            error: runtimeError,
            fallbackMessage: toTrimmedString(config.failMessage) || i18n.t('common.errors.unknownError'),
            rawMessage: true,
            showNotification: (message, level): void => host.showNotification(message, level)
        });
    } finally {
        if (config.onAfter) config.onAfter();
    }

    if (cancelled || detached) {
        return;
    }

    if (!success) {
        if (config.onFailure) config.onFailure();
        return;
    }

    const defaultOk = toTrimmedString(config.okMessage);
    const okMessage = completionMessage || defaultOk;
    host.showNotification(okMessage, isCompleteEvent ? 'success' : 'info');
    if (isCompleteEvent && config.onSuccess) config.onSuccess();
};

export { runBackendOperation };
