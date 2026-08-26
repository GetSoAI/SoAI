/* SoAI - Model test modal effects [frontend/assets/ts/features/modeldetail/modals/testmodalmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getLogValidation } from '@core/logvalidation/public.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { runOpenAiModelTestStream } from '@core/openai/modelTestStreamClient.ts';
import type { TestModalRuntimeContext } from '@features/modeldetail/modals/testmodalmanager/internalContracts.ts';
import { appendResponseText, updateRequestDetails } from '@features/modeldetail/modals/testmodalmanager/requestDetails.ts';
import { appendLogEntry, resolveModelPluginName } from '@features/modeldetail/modals/testmodalmanager/view.ts';
import type { TestModalStreamRequest } from '@features/modeldetail/modals/TestModalManagerTypes.ts';

const MODEL_TEST_LOG_HISTORY_LIMIT = 1;

export const ensureLogStream = (context: TestModalRuntimeContext): void => {
    const pluginName = resolveModelPluginName(context);
    if (!pluginName || pluginName === 'virtual') {
        return;
    }

    if (context.state.logStreamHandle && context.state.logStreamPluginName !== pluginName) {
        teardownLogStream(context);
    }

    if (context.state.logStreamHandle || context.state.logStreamCallback) {
        return;
    }

    context.state.logStreamPluginName = pluginName;
    context.state.logStreamCallback = (payload: JsonValue | null | undefined): void => {
        if (!payload || !isObject(payload)) {
            return;
        }

        const mode = payload['mode'];
        if (String(mode || '').toLowerCase() === 'history') {
            return;
        }

        const entriesValue = payload['entries'];
        if (!isArray(entriesValue)) {
            return;
        }

        entriesValue.forEach((entry: JsonValue | null | undefined): void => {
            const result = getLogValidation().validateLogEntry(entry);
            const resultObject = isObject(result) ? result : null;
            if (resultObject?.['valid'] && resultObject['entry']) {
                appendLogEntry(context, entry);
            }
        });
    };

    context.state.logStreamHandle = context.host.model.streamLogs(
        pluginName,
        {
            onUpdate: (data: JsonValue | null | undefined): void => {
                try {
                    if (context.state.logStreamCallback) {
                        context.state.logStreamCallback(data);
                    }
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug('TestModalManager', 'Test log stream handler failed', runtimeError);
                }
            },
            onError: (error: Error | string | null): void => errorHandler.debug('TestModalManager', 'Test log stream encountered error', error)
        },
        {
            historyLimit: MODEL_TEST_LOG_HISTORY_LIMIT
        }
    );
};

export const teardownLogStream = (context: TestModalRuntimeContext): void => {
    if (context.state.logStreamHandle) {
        context.state.logStreamHandle.close();
    }
    context.state.logStreamHandle = null;
    context.state.logStreamCallback = null;
    context.state.logStreamPluginName = null;
};

export const updatePluginStatusDisplay = (context: TestModalRuntimeContext, onPluginError: (message: string) => void): void => {
    const statusContainer = context.host.view.optionalUI(modalUiSelector(context.modalId, 'plugin-status'), context.modalRoot);
    const statusText = context.host.view.optionalUI(modalUiSelector(context.modalId, 'plugin-status-text'), context.modalRoot);
    const statusLed = context.host.view.optionalUI(modalUiSelector(context.modalId, 'plugin-status-led'), context.modalRoot);
    const loadedBadge = context.host.view.optionalUI(modalUiSelector(context.modalId, 'model-loaded'), context.modalRoot);
    const modelStatusText = context.host.view.optionalUI(modalUiSelector(context.modalId, 'model-status-text'), context.modalRoot);
    const modelStatusLed = context.host.view.optionalUI(modalUiSelector(context.modalId, 'model-status-led'), context.modalRoot);

    if (!statusContainer) {
        return;
    }

    const status = context.host.model.getPluginStatus();
    const statusName = status || '';
    const description = statusName ? context.host.workflow.statusManager?.getDescription(statusName) || statusName : i18n.t('common.unknown');
    const statusManager = context.host.workflow.statusManager;

    let colorClass = 'grey';
    if (statusManager && statusName) {
        const badge = statusManager.createStatusBadge(statusName, description);
        colorClass = statusManager.allowedColors?.find((key: string): boolean => badge.classList.contains(key)) || 'grey';
    }

    context.host.view.updateProperty(statusContainer, 'className', `ui-status-badge plugin-status-badge ${colorClass}`);
    if (statusLed) {
        context.host.view.updateProperty(statusLed, 'className', `status-indicator ${colorClass}`);
    }
    if (statusText) {
        context.host.view.updateText(statusText, description);
    }

    if (loadedBadge) {
        let isLoaded = false;
        if (statusManager && status) {
            const normalized = String(statusManager.normalizeStatus(status)).toUpperCase();
            if (['READY', 'READY_DIRTY', 'READY_PENDING_DISPATCH', 'PROCESSING'].includes(normalized)) {
                isLoaded = true;
            }
        }

        const modelColorClass = isLoaded ? 'green' : 'grey';
        const modelStatusLabel = isLoaded ? i18n.t('modelDetail.modal.test.modelLoaded') : i18n.t('modelDetail.modal.test.modelNotLoaded');

        context.host.view.updateProperty(loadedBadge, 'className', `ui-status-badge plugin-status-badge ${modelColorClass}`);
        if (modelStatusLed) {
            context.host.view.updateProperty(modelStatusLed, 'className', `status-indicator ${modelColorClass}`);
        }
        if (modelStatusText) {
            context.host.view.updateText(modelStatusText, modelStatusLabel);
        }
    }

    if (context.state.active && statusName && statusManager?.isError?.(statusName)) {
        context.state.hasPluginError = true;
        onPluginError(i18n.t('modelDetail.modal.test.errorPlugin'));
    }
};

export const runModelTestStream = async (context: TestModalRuntimeContext, request: TestModalStreamRequest, signal: AbortSignal, runSequence: number, getLatestRunSequence: () => number): Promise<void> => {
    if (signal.aborted) {
        throw new Error('Test stream aborted before starting');
    }
    const currentRequest = context.state.currentRequest;
    if (!currentRequest || !isString(currentRequest.id) || !currentRequest.id.trim()) {
        throw new Error('Test stream requires an active request id');
    }
    const runId = currentRequest.id.trim();

    await runOpenAiModelTestStream({
        runId,
        request,
        signal,
        cancelReason: 'Model test stream cancelled by the user.',
        isActive: () => runSequence === getLatestRunSequence(),
        errorMessageFallback: i18n.t('modelDetail.modal.test.errorGeneric'),
        onAssistantTextDelta: (delta) => {
            appendResponseText(context, delta);
        }
    });

    updateRequestDetails(context);
};
