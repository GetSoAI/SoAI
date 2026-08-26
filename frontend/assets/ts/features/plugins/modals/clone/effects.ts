/* SoAI - Plugins feature clone effects [frontend/assets/ts/features/plugins/modals/clone/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { pluginClonePath } from '@core/api/endpoints/uiPaths.ts';
import { taskProgressPayloadToOperationProgress } from '@core/operationprogress/taskProgressAdapter.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { executeMutationWithClockRecovery } from '@core/mutations/mutationExecution.ts';
import { serializeClonePluginRequest } from '@core/plugins/pluginMutationContracts.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { createPluginCloneOperationKey, resolvePluginDisplayName } from '@features/plugins/modals/clone/service.ts';
import type { CloneActionContext } from '@features/plugins/modals/clone/types.ts';

const executePluginCloneAction = async ({ host, plugin, cloneOptions, modalId, startButton, setCloneControlDisabled, requireCloneProgressReporter }: CloneActionContext): Promise<void> => {
    if (!plugin?.name) {
        throw new Error('CloneManager clone operation requires a plugin name');
    }
    const pluginName = plugin.name;

    const cloneModels = cloneOptions.cloneModels === true;
    const targetName = cloneOptions.targetName ? cloneOptions.targetName : null;
    const cloneKey = createPluginCloneOperationKey(pluginName);
    const displayName = resolvePluginDisplayName(plugin, host.policy.formatPluginName);
    const cloneMessage = i18n.t('plugins.loading.cloningPlugin');

    setCloneControlDisabled(startButton, true);
    host.execution.setPluginProgressMeta(cloneKey, {
        type: 'plugin-clone',
        pluginName: plugin.name,
        displayName
    });
    requireCloneProgressReporter().update(cloneKey, {
        progress: 0,
        message: cloneMessage,
        state: 'info'
    });

    const handlers = host.execution.createStreamHandlers(cloneKey, cloneMessage, {
        onProgress: (data: JsonValue | null | undefined) => {
            if (isPlainObject(data)) {
                requireCloneProgressReporter().update(cloneKey, taskProgressPayloadToOperationProgress(data));
            }
        }
    });

    let hasError = false;
    let cancelled = false;
    let detached = false;
    let completionMessage = '';
    let isCompleteEvent = false;

    try {
        const accepted = await executeMutationWithClockRecovery(async (taskId) => {
            const requestBody = serializeClonePluginRequest({
                cloneModels,
                taskId,
                ...(targetName ? { targetName } : {})
            });
            const stream = await host.execution.startTaskAction(pluginClonePath(pluginName), {
                method: 'POST',
                body: requestBody,
                handlers,
                operation: {
                    type: 'plugin-clone',
                    pluginName,
                    plugin: pluginName,
                    displayName,
                    message: cloneMessage,
                    cancelable: false,
                    operationKey: cloneKey,
                    requestId: taskId
                }
            });
            if (!stream.accepted) throw new Error('Clone task did not expose accepted task ownership');
            await stream.accepted;
            return stream;
        });
        const settled = await settleTrackedTaskStream({
            tracker: host.execution.streams,
            stream: accepted,
            keyPrefix: cloneKey,
            failMessage: i18n.t('common.errors.unknownError')
        });
        cancelled = settled.cancelled;
        detached = settled.detached;
        completionMessage = settled.message;
        isCompleteEvent = settled.isCompleteEvent;
    } catch (error) {
        hasError = true;
        const runtimeError = ensureError(error);
        errorHandler.error('CloneManager', 'Failed to clone plugin', runtimeError);
        showOperationFailureNotification({
            error: runtimeError,
            operation: i18n.t('plugins.actions.clonePlugin'),
            fallbackMessage: i18n.t('common.errors.unknownError'),
            showNotification: (message, level): void => host.policy.showNotification(message, level)
        });
    } finally {
        host.execution.consumePluginProgressMeta(cloneKey);
        requireCloneProgressReporter().remove(cloneKey);
        setCloneControlDisabled(startButton, false);
    }

    if (hasError || cancelled || detached) {
        return;
    }

    host.policy.showNotification(
        completionMessage
            ? completionMessage
            : i18n.t('plugins.notifications.cloneSuccess', {
                  plugin: pluginName
              }),
        isCompleteEvent ? 'success' : 'info'
    );

    if (isCompleteEvent) {
        host.view.modals.close(modalId);
    }
};

export { executePluginCloneAction };
